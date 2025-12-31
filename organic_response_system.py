"""Organic Response System (ORS).

An evolution of the Proactive Conversation Engine into a continuous awareness loop
that builds understanding over time and reaches out with purpose.

Philosophy: Reach out when there's genuine reason - not on a schedule.
Be like a thoughtful friend who texts at the right moment.

State Machine:
    WAIT  - No action needed. Stay quiet, but keep gathering context.
    THINK - Something's brewing. Process and file it away as a note.
    SPEAK - There's a reason to reach out now with clear purpose.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

from config.logging import get_logger
from db.connection import SessionLocal
from db.models import (
    ProactiveAssessment,
    ProactiveMessage,
    ProactiveNote,
    UserInteractionPattern,
)

if TYPE_CHECKING:
    from discord import Client

logger = get_logger("ors")

# =============================================================================
# Configuration
# =============================================================================

ORS_ENABLED = os.getenv("ORS_ENABLED", os.getenv("PROACTIVE_ENABLED", "false")).lower() == "true"
ORS_BASE_INTERVAL_MINUTES = int(os.getenv("ORS_BASE_INTERVAL_MINUTES", "15"))
ORS_MIN_SPEAK_GAP_HOURS = float(os.getenv("ORS_MIN_SPEAK_GAP_HOURS", "2"))
ORS_ACTIVE_DAYS = int(os.getenv("ORS_ACTIVE_DAYS", "7"))
ORS_NOTE_DECAY_DAYS = int(os.getenv("ORS_NOTE_DECAY_DAYS", "7"))  # Days before note relevance decays to 0


# =============================================================================
# State Machine
# =============================================================================


class ORSState(Enum):
    """ORS state machine states."""
    WAIT = "wait"    # No action needed, observe
    THINK = "think"  # Process and file observation
    SPEAK = "speak"  # Reach out with purpose


@dataclass
class ORSDecision:
    """Result of the action decision phase."""
    state: ORSState
    reasoning: str
    note_content: str | None = None  # If THINK - what to file
    message: str | None = None  # If SPEAK - what to say
    message_purpose: str | None = None  # If SPEAK - why reaching out
    next_check_minutes: int = 15  # Suggested interval until next check


@dataclass
class ORSContext:
    """Full context for ORS decision making."""
    user_id: str
    current_time: datetime

    # Temporal
    time_since_last_interaction: timedelta | None = None
    time_since_last_proactive: timedelta | None = None
    is_active_hours: bool = True
    day_of_week: str = ""

    # Conversation
    last_interaction_summary: str | None = None
    last_interaction_energy: str | None = None
    last_interaction_channel: str | None = None
    open_threads: list[str] = field(default_factory=list)

    # Calendar (if available)
    upcoming_events: list[dict] = field(default_factory=list)

    # Notes
    pending_notes: list[dict] = field(default_factory=list)

    # Patterns
    proactive_response_rate: int | None = None
    preferred_times: dict | None = None
    explicit_boundaries: dict | None = None
    recent_proactive_ignored: bool = False

    # History
    recent_proactive_history: list[dict] = field(default_factory=list)


# =============================================================================
# Prompts
# =============================================================================

SITUATION_ASSESSMENT_PROMPT = """You are maintaining awareness of a user's context. Based on the following information, provide your current assessment of their situation.

CONTEXT:
- Current time: {current_time} ({day_of_week})
- Last interaction: {last_interaction_time} ({time_since_last})
- Last interaction summary: {last_summary}
- Last interaction energy: {last_energy}
- Calendar (next 24h): {calendar_events}
- Open threads/topics: {open_threads}
- Accumulated notes: {pending_notes}
- Proactive response rate: {response_rate}%
- Recent proactive history: {proactive_history}

ASSESS:
1. What's likely going on with them right now?
2. Are there any open loops or unresolved threads?
3. Is there anything time-sensitive coming up?
4. What's my current level of understanding (high/medium/low)?
5. Any dots connecting between recent events?

Provide a concise assessment (2-3 paragraphs). Focus on what matters for deciding whether to reach out."""

ACTION_DECISION_PROMPT = """Based on your situation assessment, decide what action to take.

ASSESSMENT:
{assessment}

CONTEXT:
- Current time: {current_time}
- Is active hours: {is_active_hours}
- Time since last proactive: {time_since_proactive}
- Recent proactive messages ignored: {recent_ignored}
- Explicit boundaries: {boundaries}

OPTIONS:
- WAIT: Nothing actionable. Stay quiet and observe.
- THINK: Something's notable. File an observation/note for later.
- SPEAK: There's a clear reason to reach out now.

GUIDELINES:
- SPEAK only when there's genuine purpose (not just "checking in")
- THINK when you notice something that might matter later
- WAIT is the default - silence is fine
- If recent proactive messages were ignored, strongly prefer WAIT
- Consider time of day and user's patterns
- Never SPEAK outside active hours unless truly urgent
- If boundaries mention avoiding certain topics, respect them

RESPOND IN THIS EXACT JSON FORMAT:
{{
    "decision": "WAIT" | "THINK" | "SPEAK",
    "reasoning": "Why this choice",
    "note": "What to file away (only if THINK)",
    "purpose": "Why reaching out (only if SPEAK)",
    "message": "What to say (only if SPEAK)",
    "next_check_minutes": 15-480
}}"""


# =============================================================================
# Context Gathering
# =============================================================================


def get_temporal_context(user_id: str) -> dict:
    """Get time-based context."""
    now = datetime.now(UTC).replace(tzinfo=None)

    with SessionLocal() as session:
        pattern = session.query(UserInteractionPattern).filter(
            UserInteractionPattern.user_id == user_id
        ).first()

        if not pattern:
            return {
                "current_time": now,
                "day_of_week": now.strftime("%A"),
                "time_since_last_interaction": None,
                "is_active_hours": True,  # Assume active if no data
            }

        time_since_last = None
        if pattern.last_interaction_at:
            time_since_last = now - pattern.last_interaction_at

        # Check if within active hours
        is_active = True
        if pattern.typical_active_hours:
            try:
                hours = json.loads(pattern.typical_active_hours)
                day_type = "weekend" if now.weekday() >= 5 else "weekday"
                active_range = hours.get(day_type, [9, 22])
                current_hour = now.hour
                is_active = active_range[0] <= current_hour <= active_range[1]
            except (json.JSONDecodeError, KeyError, IndexError):
                pass

        return {
            "current_time": now,
            "day_of_week": now.strftime("%A"),
            "time_since_last_interaction": time_since_last,
            "is_active_hours": is_active,
            "last_interaction_summary": pattern.last_interaction_summary,
            "last_interaction_energy": pattern.last_interaction_energy,
            "last_interaction_channel": pattern.last_interaction_channel,
        }


async def get_calendar_context(user_id: str) -> list[dict]:
    """Get upcoming calendar events (if Google Calendar connected)."""
    try:
        from tools.google_oauth import get_valid_token, is_configured

        if not is_configured():
            return []

        token = await get_valid_token(user_id)
        if not token:
            return []

        # Fetch next 24 hours of events
        import httpx
        now = datetime.now(UTC)
        time_max = now + timedelta(hours=24)

        params = {
            "maxResults": 10,
            "orderBy": "startTime",
            "singleEvents": True,
            "timeMin": now.isoformat(),
            "timeMax": time_max.isoformat(),
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
                timeout=10.0,
            )

            if response.status_code != 200:
                return []

            data = response.json()
            events = []
            for event in data.get("items", []):
                start = event.get("start", {})
                events.append({
                    "summary": event.get("summary", "(No title)"),
                    "start": start.get("dateTime", start.get("date")),
                    "description": (event.get("description", "") or "")[:100],
                })
            return events

    except Exception as e:
        logger.debug(f"Calendar context error: {e}")
        return []


def get_notes_context(user_id: str) -> list[dict]:
    """Get pending notes that haven't been surfaced or archived."""
    with SessionLocal() as session:
        notes = session.query(ProactiveNote).filter(
            ProactiveNote.user_id == user_id,
            ProactiveNote.surfaced == "false",
            ProactiveNote.archived == "false",
        ).order_by(ProactiveNote.relevance_score.desc()).limit(10).all()

        return [
            {
                "id": n.id,
                "note": n.note,
                "relevance": n.relevance_score,
                "surface_conditions": n.surface_conditions,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in notes
        ]


def get_patterns_context(user_id: str) -> dict:
    """Get learned interaction patterns."""
    with SessionLocal() as session:
        pattern = session.query(UserInteractionPattern).filter(
            UserInteractionPattern.user_id == user_id
        ).first()

        if not pattern:
            return {}

        return {
            "proactive_response_rate": pattern.proactive_response_rate,
            "preferred_times": json.loads(pattern.preferred_proactive_times) if pattern.preferred_proactive_times else None,
            "topic_receptiveness": json.loads(pattern.topic_receptiveness) if pattern.topic_receptiveness else None,
            "explicit_boundaries": json.loads(pattern.explicit_boundaries) if pattern.explicit_boundaries else None,
        }


def get_proactive_history(user_id: str, limit: int = 5) -> list[dict]:
    """Get recent proactive message history."""
    with SessionLocal() as session:
        messages = session.query(ProactiveMessage).filter(
            ProactiveMessage.user_id == user_id
        ).order_by(ProactiveMessage.sent_at.desc()).limit(limit).all()

        return [
            {
                "message": m.message[:100],
                "sent_at": m.sent_at.isoformat() if m.sent_at else None,
                "response_received": m.response_received == "true",
                "reason": m.reason,
            }
            for m in messages
        ]


async def gather_full_context(user_id: str) -> ORSContext:
    """Gather all context sources into ORSContext."""
    temporal = get_temporal_context(user_id)
    calendar = await get_calendar_context(user_id)
    notes = get_notes_context(user_id)
    patterns = get_patterns_context(user_id)
    history = get_proactive_history(user_id)

    # Check if recent proactive messages were ignored
    recent_ignored = False
    if history:
        recent = history[:3]
        ignored_count = sum(1 for h in recent if not h.get("response_received"))
        recent_ignored = ignored_count >= 2

    # Time since last proactive
    time_since_proactive = None
    if history and history[0].get("sent_at"):
        try:
            last_sent = datetime.fromisoformat(history[0]["sent_at"])
            time_since_proactive = temporal["current_time"] - last_sent
        except (ValueError, TypeError):
            pass

    return ORSContext(
        user_id=user_id,
        current_time=temporal["current_time"],
        time_since_last_interaction=temporal.get("time_since_last_interaction"),
        time_since_last_proactive=time_since_proactive,
        is_active_hours=temporal.get("is_active_hours", True),
        day_of_week=temporal.get("day_of_week", ""),
        last_interaction_summary=temporal.get("last_interaction_summary"),
        last_interaction_energy=temporal.get("last_interaction_energy"),
        last_interaction_channel=temporal.get("last_interaction_channel"),
        upcoming_events=calendar,
        pending_notes=notes,
        proactive_response_rate=patterns.get("proactive_response_rate"),
        preferred_times=patterns.get("preferred_times"),
        explicit_boundaries=patterns.get("explicit_boundaries"),
        recent_proactive_ignored=recent_ignored,
        recent_proactive_history=history,
    )


# =============================================================================
# Decision Logic
# =============================================================================


async def assess_situation(context: ORSContext, llm_call: Callable) -> str:
    """Phase 2: Generate situation assessment."""
    # Format context for prompt
    time_since = "Unknown"
    if context.time_since_last_interaction:
        hours = context.time_since_last_interaction.total_seconds() / 3600
        if hours < 1:
            time_since = f"{int(hours * 60)} minutes ago"
        elif hours < 24:
            time_since = f"{hours:.1f} hours ago"
        else:
            time_since = f"{hours / 24:.1f} days ago"

    calendar_str = "No calendar access"
    if context.upcoming_events:
        calendar_str = "\n".join(
            f"- {e['summary']} at {e['start']}"
            for e in context.upcoming_events[:5]
        )
    elif context.upcoming_events == []:
        calendar_str = "No upcoming events in next 24h"

    notes_str = "No pending notes"
    if context.pending_notes:
        notes_str = "\n".join(
            f"- {n['note']} (relevance: {n['relevance']})"
            for n in context.pending_notes[:5]
        )

    history_str = "No recent proactive messages"
    if context.recent_proactive_history:
        history_str = "\n".join(
            f"- \"{h['message']}\" ({'got response' if h['response_received'] else 'no response'})"
            for h in context.recent_proactive_history[:3]
        )

    prompt = SITUATION_ASSESSMENT_PROMPT.format(
        current_time=context.current_time.strftime("%Y-%m-%d %H:%M"),
        day_of_week=context.day_of_week,
        last_interaction_time=time_since,
        time_since_last=time_since,
        last_summary=context.last_interaction_summary or "No recent interaction",
        last_energy=context.last_interaction_energy or "Unknown",
        calendar_events=calendar_str,
        open_threads="None tracked",  # TODO: Implement open thread detection
        pending_notes=notes_str,
        response_rate=context.proactive_response_rate or "Unknown",
        proactive_history=history_str,
    )

    messages = [{"role": "user", "content": prompt}]
    response = await llm_call(messages)
    return response


async def decide_action(
    context: ORSContext,
    assessment: str,
    llm_call: Callable,
) -> ORSDecision:
    """Phase 3: Decide WAIT/THINK/SPEAK based on assessment."""
    time_since_proactive = "Unknown"
    if context.time_since_last_proactive:
        hours = context.time_since_last_proactive.total_seconds() / 3600
        time_since_proactive = f"{hours:.1f} hours"

    boundaries_str = "None set"
    if context.explicit_boundaries:
        boundaries_str = json.dumps(context.explicit_boundaries)

    prompt = ACTION_DECISION_PROMPT.format(
        assessment=assessment,
        current_time=context.current_time.strftime("%Y-%m-%d %H:%M"),
        is_active_hours=context.is_active_hours,
        time_since_proactive=time_since_proactive,
        recent_ignored=context.recent_proactive_ignored,
        boundaries=boundaries_str,
    )

    messages = [{"role": "user", "content": prompt}]
    response = await llm_call(messages)

    # Parse JSON response
    try:
        # Find JSON in response
        import re
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            data = json.loads(json_match.group())
        else:
            raise ValueError("No JSON found in response")

        decision_str = data.get("decision", "WAIT").upper()
        state = ORSState[decision_str] if decision_str in ORSState.__members__ else ORSState.WAIT

        return ORSDecision(
            state=state,
            reasoning=data.get("reasoning", ""),
            note_content=data.get("note") if state == ORSState.THINK else None,
            message=data.get("message") if state == ORSState.SPEAK else None,
            message_purpose=data.get("purpose") if state == ORSState.SPEAK else None,
            next_check_minutes=int(data.get("next_check_minutes", 15)),
        )
    except Exception as e:
        logger.warning(f"Failed to parse decision response: {e}")
        return ORSDecision(
            state=ORSState.WAIT,
            reasoning=f"Parse error, defaulting to WAIT: {e}",
            next_check_minutes=15,
        )


# =============================================================================
# Adaptive Timing
# =============================================================================


def calculate_next_check(context: ORSContext, decision: ORSDecision) -> int:
    """Calculate adaptive interval until next check (in minutes)."""
    base = ORS_BASE_INTERVAL_MINUTES

    # Start with LLM suggestion if reasonable
    suggested = decision.next_check_minutes
    if 5 <= suggested <= 480:
        base = suggested

    # Adjustments based on context
    multiplier = 1.0

    # Outside active hours - check less often
    if not context.is_active_hours:
        multiplier *= 4.0

    # Recent proactive ignored - back off
    if context.recent_proactive_ignored:
        multiplier *= 2.0

    # Has urgent pending notes - check more often
    if context.pending_notes:
        high_relevance = any(n.get("relevance", 0) > 80 for n in context.pending_notes)
        if high_relevance:
            multiplier *= 0.5

    # Upcoming event soon - check more often
    if context.upcoming_events:
        # Check if any event is within 2 hours
        now = context.current_time
        for event in context.upcoming_events:
            try:
                start_str = event.get("start", "")
                if "T" in start_str:
                    start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    if start.tzinfo:
                        start = start.replace(tzinfo=None)
                    if (start - now).total_seconds() < 7200:  # 2 hours
                        multiplier *= 0.5
                        break
            except (ValueError, TypeError):
                continue

    # Calculate final interval
    final = int(base * multiplier)

    # Clamp to reasonable bounds
    return max(5, min(480, final))  # 5 min to 8 hours


# =============================================================================
# Note Management
# =============================================================================


def create_note(
    user_id: str,
    content: str,
    source_context: dict | None = None,
    surface_conditions: str | None = None,
) -> str:
    """Create a new internal note from THINK state."""
    with SessionLocal() as session:
        note = ProactiveNote(
            user_id=user_id,
            note=content,
            source_context=json.dumps(source_context) if source_context else None,
            surface_conditions=surface_conditions,
            relevance_score=100,
        )
        session.add(note)
        session.commit()
        logger.info(f"Created note for {user_id}: {content[:50]}...")
        return note.id


def decay_note_relevance():
    """Decay relevance of old notes (run periodically)."""
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=ORS_NOTE_DECAY_DAYS)

    with SessionLocal() as session:
        # Decay notes older than cutoff
        old_notes = session.query(ProactiveNote).filter(
            ProactiveNote.created_at < cutoff,
            ProactiveNote.surfaced == "false",
            ProactiveNote.archived == "false",
            ProactiveNote.relevance_score > 0,
        ).all()

        for note in old_notes:
            days_old = (datetime.now(UTC).replace(tzinfo=None) - note.created_at).days
            decay_factor = max(0, 1 - (days_old / (ORS_NOTE_DECAY_DAYS * 2)))
            note.relevance_score = int(100 * decay_factor)

            # Archive if relevance hits 0
            if note.relevance_score <= 0:
                note.archived = "true"
                logger.debug(f"Archived stale note: {note.id}")

        session.commit()


def mark_note_surfaced(note_id: str):
    """Mark a note as surfaced after being mentioned."""
    with SessionLocal() as session:
        note = session.query(ProactiveNote).filter(ProactiveNote.id == note_id).first()
        if note:
            note.surfaced = "true"
            note.surfaced_at = datetime.now(UTC).replace(tzinfo=None)
            session.commit()


# =============================================================================
# Assessment Recording
# =============================================================================


def record_assessment(
    user_id: str,
    context: ORSContext,
    assessment: str,
    decision: ORSDecision,
    note_id: str | None = None,
) -> str:
    """Record an assessment for continuity and debugging."""
    with SessionLocal() as session:
        record = ProactiveAssessment(
            user_id=user_id,
            context_snapshot=json.dumps({
                "time_since_last_interaction": str(context.time_since_last_interaction),
                "is_active_hours": context.is_active_hours,
                "pending_notes_count": len(context.pending_notes),
                "upcoming_events_count": len(context.upcoming_events),
                "recent_proactive_ignored": context.recent_proactive_ignored,
            }),
            assessment=assessment,
            decision=decision.state.value,
            reasoning=decision.reasoning,
            note_created=note_id,
            message_sent=decision.message if decision.state == ORSState.SPEAK else None,
            next_check_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(
                minutes=decision.next_check_minutes
            ),
        )
        session.add(record)
        session.commit()
        return record.id


# =============================================================================
# Message Sending
# =============================================================================


async def send_proactive_message(
    client: Client,
    user_id: str,
    channel_id: str,
    message: str,
    purpose: str,
) -> bool:
    """Send a proactive message and record it."""
    try:
        # Parse channel ID
        if channel_id.startswith("discord-dm-"):
            # DM to user
            discord_user_id = int(channel_id.replace("discord-dm-", "").replace("discord-", ""))
            user = await client.fetch_user(discord_user_id)
            dm = await user.create_dm()
            await dm.send(message)
        elif channel_id.startswith("discord-channel-"):
            # Channel message
            discord_channel_id = int(channel_id.replace("discord-channel-", ""))
            channel = client.get_channel(discord_channel_id)
            if channel:
                await channel.send(message)
            else:
                logger.warning(f"Channel not found: {channel_id}")
                return False
        else:
            logger.warning(f"Unknown channel format: {channel_id}")
            return False

        # Record the message
        with SessionLocal() as session:
            record = ProactiveMessage(
                user_id=user_id,
                channel_id=channel_id,
                message=message,
                priority="normal",
                reason=purpose,
            )
            session.add(record)
            session.commit()

        logger.info(f"Sent proactive message to {user_id}: {message[:50]}...")
        return True

    except Exception as e:
        logger.error(f"Failed to send proactive message: {e}")
        return False


# =============================================================================
# Main Loop
# =============================================================================


def is_enabled() -> bool:
    """Check if ORS is enabled."""
    return ORS_ENABLED


def get_active_users() -> list[str]:
    """Get users who have been active recently."""
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=ORS_ACTIVE_DAYS)

    with SessionLocal() as session:
        patterns = session.query(UserInteractionPattern).filter(
            UserInteractionPattern.last_interaction_at > cutoff
        ).all()

        return [p.user_id for p in patterns]


async def process_user(
    user_id: str,
    client: Client,
    llm_call: Callable,
) -> int:
    """Process ORS cycle for a single user. Returns minutes until next check."""
    logger.debug(f"Processing ORS for user: {user_id}")

    # Phase 1: Gather context
    context = await gather_full_context(user_id)

    # Phase 2: Assess situation
    assessment = await assess_situation(context, llm_call)

    # Phase 3: Decide action
    decision = await decide_action(context, assessment, llm_call)

    # Phase 4: Execute
    note_id = None

    if decision.state == ORSState.THINK and decision.note_content:
        # File the observation
        note_id = create_note(
            user_id=user_id,
            content=decision.note_content,
            source_context={"assessment": assessment[:200]},
        )
        logger.info(f"ORS THINK for {user_id}: {decision.note_content[:50]}...")

    elif decision.state == ORSState.SPEAK and decision.message:
        # Check minimum gap since last proactive
        can_speak = True
        if context.time_since_last_proactive:
            hours_since = context.time_since_last_proactive.total_seconds() / 3600
            if hours_since < ORS_MIN_SPEAK_GAP_HOURS:
                can_speak = False
                logger.info(
                    f"ORS SPEAK blocked for {user_id}: "
                    f"only {hours_since:.1f}h since last (min: {ORS_MIN_SPEAK_GAP_HOURS}h)"
                )

        if can_speak and context.last_interaction_channel:
            success = await send_proactive_message(
                client=client,
                user_id=user_id,
                channel_id=context.last_interaction_channel,
                message=decision.message,
                purpose=decision.message_purpose or decision.reasoning,
            )
            if success:
                logger.info(f"ORS SPEAK for {user_id}: {decision.message[:50]}...")

    else:
        logger.debug(f"ORS WAIT for {user_id}: {decision.reasoning[:50]}...")

    # Record assessment
    record_assessment(user_id, context, assessment, decision, note_id)

    # Calculate adaptive timing
    return calculate_next_check(context, decision)


async def ors_main_loop(client: Client, llm_call: Callable):
    """Main ORS loop - runs continuously with adaptive timing."""
    logger.info("ORS main loop starting")

    # Track next check time per user
    next_checks: dict[str, datetime] = {}

    while True:
        try:
            now = datetime.now(UTC).replace(tzinfo=None)

            # Get active users
            users = get_active_users()
            if not users:
                logger.debug("No active users, sleeping 15 minutes")
                await asyncio.sleep(900)
                continue

            # Decay old note relevance periodically
            decay_note_relevance()

            # Process users whose next check time has passed
            for user_id in users:
                next_check = next_checks.get(user_id)

                if next_check and now < next_check:
                    continue  # Not time yet for this user

                try:
                    minutes_until_next = await process_user(user_id, client, llm_call)
                    next_checks[user_id] = now + timedelta(minutes=minutes_until_next)
                except Exception as e:
                    logger.error(f"Error processing user {user_id}: {e}")
                    next_checks[user_id] = now + timedelta(minutes=30)  # Retry in 30 min

                # Small delay between users to avoid rate limits
                await asyncio.sleep(2)

            # Sleep until next user needs checking (or 5 min max)
            if next_checks:
                soonest = min(next_checks.values())
                sleep_seconds = max(60, min(300, (soonest - now).total_seconds()))
            else:
                sleep_seconds = 300

            logger.debug(f"ORS sleeping {sleep_seconds / 60:.1f} minutes")
            await asyncio.sleep(sleep_seconds)

        except Exception as e:
            logger.error(f"ORS loop error: {e}")
            await asyncio.sleep(60)


# =============================================================================
# Public API (backwards compatible with proactive_engine.py)
# =============================================================================


async def on_user_message(
    user_id: str,
    channel_id: str,
    message_preview: str | None = None,
):
    """Called when user sends a message - updates interaction patterns."""
    now = datetime.now(UTC).replace(tzinfo=None)

    with SessionLocal() as session:
        pattern = session.query(UserInteractionPattern).filter(
            UserInteractionPattern.user_id == user_id
        ).first()

        if not pattern:
            pattern = UserInteractionPattern(user_id=user_id)
            session.add(pattern)

        pattern.last_interaction_at = now
        pattern.last_interaction_channel = channel_id
        session.commit()


# Alias for backwards compatibility
proactive_check_loop = ors_main_loop
