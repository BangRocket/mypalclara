"""Game move API for Clara's Game Room."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)

router = APIRouter()

VALID_PERSONALITIES = {"clara", "flo", "clarissa"}
VALID_MOODS = {"idle", "happy", "nervous", "smug", "surprised", "defeated"}
PERSONALITIES_DIR = Path(__file__).parent.parent.parent.parent / "personalities"


class GameMoveRequest(BaseModel):
    game_type: str
    game_state: dict[str, Any]
    legal_moves: list[str]
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


def _verify_api_key(x_game_api_key: str | None = Header(None)) -> None:
    """Verify the game API key from the request header."""
    expected = os.getenv("GAME_API_KEY")
    if not expected or x_game_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def _load_personality_text(personality: str) -> str:
    """Load personality file content."""
    path = PERSONALITIES_DIR / f"{personality}.md"
    if not path.exists():
        logger.warning("Personality file not found: %s, using clara", path)
        path = PERSONALITIES_DIR / "clara.md"
    return path.read_text(encoding="utf-8").strip()


async def get_clara_move(
    request: GameMoveRequest,
    personality_text: str,
) -> dict[str, Any]:
    """Call the LLM to get Clara's game move and commentary."""
    from mypalclara.core.llm import make_llm

    llm = make_llm(tier="mid")

    # Fetch user memories for context
    user_memories: list[str] = []
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
{{"move": {{"type": "<your chosen move>"}}, "commentary": "<your in-character reaction>", "mood": "<one of: idle, happy, nervous, smug, surprised, defeated>"}}"""

    try:
        messages = [{"role": "user", "content": prompt}]
        content = await asyncio.to_thread(llm, messages)

        result = json.loads(content)

        move_type = result.get("move", {}).get("type", "")
        if move_type not in request.legal_moves:
            logger.warning("Clara returned illegal move: %s, picking random", move_type)
            result["move"] = {"type": random.choice(request.legal_moves)}
            result["commentary"] = "Hmm, let me think... okay, I'll do this."

        if result.get("mood") not in VALID_MOODS:
            result["mood"] = "idle"

        return result

    except Exception:
        logger.exception("Failed to get LLM game move")
        return {
            "move": {"type": random.choice(request.legal_moves)},
            "commentary": "Give me a second... okay, here goes.",
            "mood": "nervous",
        }


@router.post("/move", response_model=GameMoveResponse)
async def game_move(
    request: GameMoveRequest,
    x_game_api_key: str | None = Header(None),
) -> GameMoveResponse:
    """Get Clara's next move and commentary for a game."""
    _verify_api_key(x_game_api_key)
    personality_text = _load_personality_text(request.personality)
    result = await get_clara_move(request, personality_text)
    return GameMoveResponse(**result)
