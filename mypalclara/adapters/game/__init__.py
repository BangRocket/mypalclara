"""Game adapter package.

Provides the game engine for Clara's Game Room — an HTTP-served adapter
that receives game state and returns LLM-driven moves with personality.

Module structure:
- engine.py: Core game logic, models, and LLM integration
- api.py: FastAPI router with /move endpoint
"""

from mypalclara.adapters.game.api import router
from mypalclara.adapters.game.engine import (
    GameMoveRequest,
    GameMoveResponse,
    get_clara_move,
)
from mypalclara.adapters.manifest import AdapterManifest, adapter


@adapter(
    AdapterManifest(
        name="game",
        platform="game",
        display_name="Game Room",
        description="HTTP game adapter for Clara's Game Room",
        icon="\U0001f3b2",
        capabilities=[],
        required_env=["GAME_API_KEY"],
        tags=["game", "http"],
    )
)
class GameAdapter:
    """Marker class for game adapter manifest registration."""


__all__ = [
    "GameAdapter",
    "GameMoveRequest",
    "GameMoveResponse",
    "get_clara_move",
    "router",
]
