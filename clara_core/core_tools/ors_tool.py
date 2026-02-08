"""ORS (Organic Response System) tool - Clara core tool.

Provides an explicit tool for Clara to assess a user and decide whether
to follow up, file a note, or stay quiet. Runs the same assess/decide
pipeline as the background ORS loop but on demand during a conversation.
"""

from __future__ import annotations

import asyncio
from typing import Any

from config.logging import get_logger
from tools._base import ToolContext, ToolDef

MODULE_NAME = "ors"
MODULE_VERSION = "1.0.0"

logger = get_logger("core_tools.ors")

SYSTEM_PROMPT = """## Proactive Follow-Up (ORS)
Use `assess_and_decide` when you notice something worth following up on -
an unresolved question, a user who might benefit from a check-in, or
a pattern worth noting. This evaluates the full context and decides
whether to WAIT, THINK (file a note), or SPEAK (schedule a message).
""".strip()


async def _handle_assess_and_decide(args: dict[str, Any], ctx: ToolContext) -> str:
    """Run the ORS assess -> decide pipeline for a user."""
    from proactive.engine import (
        ORSState,
        assess_situation,
        create_note,
        decide_action,
        gather_full_context,
        get_ors_model_name,
        is_enabled,
        record_assessment,
        send_proactive_message,
    )

    if not is_enabled():
        return "ORS is not enabled. Set PROACTIVE_ENABLED=true to use this tool."

    user_id = args.get("user_id") or ctx.user_id
    reason = args.get("reason", "")
    channel_id = args.get("channel_id") or ctx.channel_id

    if not user_id or user_id == "default":
        return "Error: user_id is required. Pass it explicitly or ensure the conversation context provides one."

    # Build an LLM callable for the ORS pipeline
    from clara_core.llm import make_llm

    async def llm_call(messages):
        loop = asyncio.get_event_loop()
        llm = make_llm()
        return await loop.run_in_executor(None, llm, messages)

    # Phase 1: Gather context (enricher is only available in the background ORS loop)
    context = await gather_full_context(user_id)

    # Phase 2: Assess situation
    assessment = await assess_situation(context, llm_call)

    # Phase 3: Decide action
    decision = await decide_action(context, assessment, llm_call)

    # Phase 4: Execute
    model_name = get_ors_model_name()
    note_id = None
    result_lines = [
        f"**ORS Assessment for {user_id}**",
        f"Decision: **{decision.state.value.upper()}**",
        f"Reasoning: {decision.reasoning}",
    ]

    if reason:
        result_lines.insert(1, f"Trigger: {reason}")

    if decision.state == ORSState.THINK and decision.note_content:
        note_id = create_note(
            user_id=user_id,
            content=decision.note_content,
            note_type=decision.note_type,
            source_context={"from": "explicit_tool", "reason": reason},
            surface_conditions=decision.note_surface_conditions,
            expires_hours=decision.note_expires_hours,
            source_model=model_name,
            source_confidence=decision.note_confidence,
            grounding_message_ids=decision.note_grounding_ids,
        )
        result_lines.append(f"Note filed: {decision.note_content}")
        if decision.note_type:
            result_lines.append(f"Note type: {decision.note_type}")

    elif decision.state == ORSState.SPEAK and decision.message:
        delivery_channel = channel_id or context.last_interaction_channel
        if delivery_channel:
            from mypalclara.gateway.scheduler import get_scheduler

            scheduler = get_scheduler()
            success = await scheduler.send_message(
                user_id=user_id,
                channel_id=delivery_channel,
                message=decision.message,
                purpose=decision.message_purpose or decision.reasoning,
            )
            if success:
                result_lines.append(f"Message sent: {decision.message}")
            else:
                result_lines.append(f"Message delivery failed (no connected adapter). Message: {decision.message}")
        else:
            result_lines.append(f"SPEAK decided but no channel available. Message: {decision.message}")

    result_lines.append(f"Next check suggested: {decision.next_check_minutes} minutes")

    # Record assessment
    record_assessment(user_id, context, assessment, decision, note_id)

    return "\n".join(result_lines)


TOOLS = [
    ToolDef(
        name="assess_and_decide",
        description=(
            "Evaluate a user's context and decide whether to follow up. "
            "Runs the ORS (Organic Response System) pipeline: gathers full context "
            "(recent messages, notes, patterns, calendar), assesses the situation, "
            "then decides to WAIT (do nothing), THINK (file a note for later), "
            "or SPEAK (send a message now)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "User to evaluate (defaults to current user)",
                },
                "reason": {
                    "type": "string",
                    "description": "Why you're considering a follow-up (provides context to the assessment)",
                },
                "channel_id": {
                    "type": "string",
                    "description": "Override delivery channel for SPEAK (defaults to current or last interaction channel)",
                },
            },
            "required": [],
        },
        handler=_handle_assess_and_decide,
        emoji="\U0001f9e0",
        label="ORS",
        detail_keys=["user_id", "reason"],
        risk_level="moderate",
        intent="write",
    ),
]


async def initialize() -> None:
    """Initialize ORS tool module."""
    pass


async def cleanup() -> None:
    """Cleanup on module unload."""
    pass
