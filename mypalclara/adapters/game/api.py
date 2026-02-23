"""Game API router — thin FastAPI layer over game engine."""

from __future__ import annotations

import os

from fastapi import APIRouter, Header

from mypalclara.adapters.game.engine import (
    GameEventRequest,
    GameEventResponse,
    GameMoveRequest,
    GameMoveResponse,
    _load_personality_text,
    _verify_api_key,
    get_clara_commentary,
    get_clara_move,
)

router = APIRouter()

_MEMORIES_ENABLED = os.getenv("GAME_MEMORIES_ENABLED", "false").lower() in ("true", "1", "yes")


@router.post("/move", response_model=GameMoveResponse)
async def game_move(
    request: GameMoveRequest,
    x_game_api_key: str | None = Header(None),
) -> GameMoveResponse:
    """Get Clara's next move and commentary for a game."""
    _verify_api_key(x_game_api_key)
    personality_text = _load_personality_text(request.personality)
    result = await get_clara_move(request, personality_text, include_memories=_MEMORIES_ENABLED)
    return GameMoveResponse(**result)


@router.post("/event", response_model=GameEventResponse)
async def game_event(
    request: GameEventRequest,
    x_game_api_key: str | None = Header(None),
) -> GameEventResponse:
    """Get Clara's commentary on a game event."""
    _verify_api_key(x_game_api_key)
    personality_text = _load_personality_text("clara")
    result = await get_clara_commentary(request, personality_text)
    return GameEventResponse(**result)
