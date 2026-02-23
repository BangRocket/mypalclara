"""Game engine — core LLM logic for Clara's game moves."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)

VALID_PERSONALITIES = {"clara", "flo", "clarissa"}
VALID_MOODS = {"idle", "happy", "nervous", "smug", "surprised", "defeated"}
PERSONALITIES_DIR = Path(__file__).parent.parent.parent.parent / "personalities"


class GameMoveRequest(BaseModel):
    game_type: str
    game_state: dict[str, Any]
    legal_moves: list[str | dict[str, Any]]
    personality: str
    user_id: str
    move_history: list[dict[str, Any]] = []

    @field_validator("personality")
    @classmethod
    def validate_personality(cls, v: str) -> str:
        if v not in VALID_PERSONALITIES:
            msg = f"Unknown personality: {v}. Must be one of: {VALID_PERSONALITIES}"
            raise ValueError(msg)
        return v


class GameMoveResponse(BaseModel):
    move: dict[str, Any]
    commentary: str
    mood: str


def _verify_api_key(x_game_api_key: str | None) -> None:
    """Verify the game API key from the request header."""
    expected = os.getenv("GAME_API_KEY")
    if not expected or x_game_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@lru_cache(maxsize=8)
def _load_personality_text(personality: str) -> str:
    """Load personality file content (cached after first read)."""
    path = PERSONALITIES_DIR / f"{personality}.md"
    if not path.exists():
        logger.warning("Personality file not found: %s, using clara", path)
        path = PERSONALITIES_DIR / "clara.md"
    return path.read_text(encoding="utf-8").strip()


def _is_legal_move(chosen: str | dict[str, Any], legal_moves: list[str | dict[str, Any]]) -> bool:
    """Check if the chosen move matches any legal move."""
    # LLM may return a bare string like "hit" instead of {"type": "hit"}
    if isinstance(chosen, str):
        return chosen in legal_moves
    # String-based moves (blackjack): {"type": "hit"} in ["hit", "stand"]
    move_type = chosen.get("type", "")
    if move_type and move_type in legal_moves:
        return True
    # Dict-based moves (checkers): match by from/to
    if "from" in chosen and "to" in chosen:
        for m in legal_moves:
            if isinstance(m, dict) and m.get("from") == chosen["from"] and m.get("to") == chosen["to"]:
                return True
    return False


async def get_clara_move(
    request: GameMoveRequest,
    personality_text: str,
    *,
    include_memories: bool = False,
) -> dict[str, Any]:
    """Call the LLM to get Clara's game move and commentary."""
    from mypalclara.core.llm import make_llm

    llm = make_llm(tier="mid")

    # Fetch user memories for context (skipped by default for latency)
    user_memories: list[str] = []
    if include_memories:
        try:
            from mypalclara.core.memory import ROOK

            if ROOK:
                results = ROOK.search(
                    f"playing {request.game_type}",
                    user_id=request.user_id,
                    agent_id="mypalclara",
                    limit=5,
                )
                user_memories = [r.get("memory", "") for r in (results or []) if r.get("memory")]
        except Exception:
            logger.debug("Could not fetch user memories for game", exc_info=True)

    memory_context = ""
    if user_memories:
        memory_context = "\n\nWhat you know about this player:\n" + "\n".join(f"- {m}" for m in user_memories)

    history_text = ""
    if request.move_history:
        recent = request.move_history[-5:]
        history_text = "\n\nRecent moves:\n" + "\n".join(f"- {m}" for m in recent)

    prompt = f"""{personality_text}
{memory_context}

You are playing {request.game_type} against a player.
Current game state: {json.dumps(request.game_state, indent=2)}
{history_text}

Your legal moves: {json.dumps(request.legal_moves)}

Pick ONE move from the legal moves list. Provide commentary in character \
-- trash talk, encouragement, nervousness, whatever fits. \
Also indicate your mood.

Respond with ONLY valid JSON (no markdown fences):
{{"move": <your chosen move from the list>, "commentary": "<your in-character reaction>", "mood": "<one of: idle, happy, nervous, smug, surprised, defeated>"}}"""

    try:
        messages = [{"role": "user", "content": prompt}]
        content = await asyncio.to_thread(llm, messages)

        # Strip markdown code fences if present
        content = re.sub(r"^```(?:json)?\s*\n?", "", content.strip())
        content = re.sub(r"\n?```\s*$", "", content.strip())

        result = json.loads(content)

        # Validate the move against legal moves
        chosen_move = result.get("move", {})
        # Normalize: if LLM returned a bare string, wrap it
        if isinstance(chosen_move, str):
            result["move"] = {"type": chosen_move}
            chosen_move = result["move"]
        if _is_legal_move(chosen_move, request.legal_moves):
            pass  # move is valid
        elif request.legal_moves:
            logger.warning("Clara returned illegal move: %s, picking random", chosen_move)
            fallback = random.choice(request.legal_moves)
            result["move"] = fallback if isinstance(fallback, dict) else {"type": fallback}
            result["commentary"] = "Hmm, let me think... okay, I'll do this."
        else:
            result["move"] = {"type": "pass"}
            result["commentary"] = "I... don't have any moves?"

        if result.get("mood") not in VALID_MOODS:
            result["mood"] = "idle"

        return result

    except Exception:
        logger.exception("Failed to get LLM game move")
        if request.legal_moves:
            fallback = random.choice(request.legal_moves)
            move = fallback if isinstance(fallback, dict) else {"type": fallback}
        else:
            move = {"type": "pass"}
        return {
            "move": move,
            "commentary": "Give me a second... okay, here goes.",
            "mood": "nervous",
        }


class GameEventRequest(BaseModel):
    event_type: str  # game_start, player_move, clara_move, player_chat, game_over
    game_type: str
    state_summary: str
    event_data: dict[str, Any] = {}
    position_eval: float = 0.0
    user_id: str
    recent_history: list[dict[str, Any]] = []


class GameEventResponse(BaseModel):
    commentary: str | None
    mood: str


async def get_clara_commentary(
    request: GameEventRequest,
    personality_text: str,
) -> dict[str, Any]:
    """Generate Clara's commentary for a game event using high-tier LLM."""
    from mypalclara.core.llm import make_llm

    tier = os.getenv("GAME_EVENT_LLM_TIER", "high")
    llm = make_llm(tier=tier)

    # Fetch user memories for richer commentary
    memory_context = ""
    if os.getenv("GAME_EVENT_MEMORIES", "true").lower() in ("true", "1", "yes"):
        try:
            from mypalclara.core.memory import ROOK

            if ROOK:
                results = ROOK.search(
                    f"playing {request.game_type} with user",
                    user_id=request.user_id,
                    agent_id="mypalclara",
                    limit=5,
                )
                memories = [r.get("memory", "") for r in (results or []) if r.get("memory")]
                if memories:
                    memory_context = "\n\nWhat you know about this player:\n" + "\n".join(
                        f"- {m}" for m in memories
                    )
        except Exception:
            logger.debug("Could not fetch user memories for game event", exc_info=True)

    # Build emotional context from position evaluation
    eval_desc = ""
    if request.position_eval > 0.5:
        eval_desc = "You're winning comfortably."
    elif request.position_eval > 0.1:
        eval_desc = "You're slightly ahead."
    elif request.position_eval > -0.1:
        eval_desc = "The game is close."
    elif request.position_eval > -0.5:
        eval_desc = "You're slightly behind."
    else:
        eval_desc = "You're losing."

    history_text = ""
    if request.recent_history:
        history_text = "\n\nRecent moves:\n" + "\n".join(
            f"- {m}" for m in request.recent_history[-5:]
        )

    event_desc = {
        "game_start": "A new game is starting.",
        "player_move": f"The player just made a move: {json.dumps(request.event_data)}",
        "clara_move": f"You just made a move: {json.dumps(request.event_data)}",
        "player_chat": f"The player says: \"{request.event_data.get('message', '')}\"",
        "game_over": f"The game is over. Result: {json.dumps(request.event_data)}",
    }.get(request.event_type, f"Game event: {request.event_type}")

    prompt = f"""{personality_text}
{memory_context}

You are playing {request.game_type}.
{request.state_summary}
{eval_desc}
{history_text}

{event_desc}

React in character. Be natural — trash talk, encouragement, \
nervousness, gloating, whatever fits your personality and the situation.

Respond with ONLY valid JSON (no markdown fences):
{{"commentary": "<your in-character reaction>", "mood": "<one of: idle, happy, nervous, smug, surprised, defeated>"}}"""

    try:
        messages = [{"role": "user", "content": prompt}]
        content = await asyncio.to_thread(llm, messages)

        content = re.sub(r"^```(?:json)?\s*\n?", "", content.strip())
        content = re.sub(r"\n?```\s*$", "", content.strip())

        result = json.loads(content)

        if result.get("mood") not in VALID_MOODS:
            result["mood"] = "idle"

        return result

    except Exception:
        logger.exception("Failed to get LLM game commentary")
        return {"commentary": None, "mood": "neutral"}
