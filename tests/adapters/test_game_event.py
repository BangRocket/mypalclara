"""Tests for the game event endpoint."""

import os
from unittest.mock import MagicMock, patch

import pytest

from mypalclara.adapters.game.engine import (
    GameEventRequest,
    GameEventResponse,
    get_clara_commentary,
)


class TestGameEventRequest:
    def test_valid_request(self):
        req = GameEventRequest(
            event_type="clara_move",
            game_type="checkers",
            state_summary="You're playing Red. 12 pieces each.",
            user_id="user-1",
        )
        assert req.event_type == "clara_move"
        assert req.position_eval == 0.0
        assert req.recent_history == []

    def test_all_fields(self):
        req = GameEventRequest(
            event_type="player_chat",
            game_type="blackjack",
            state_summary="Your hand: K, 7 (17).",
            event_data={"message": "nice move!"},
            position_eval=-0.3,
            user_id="user-1",
            recent_history=[{"action": "hit"}],
        )
        assert req.event_data == {"message": "nice move!"}
        assert req.position_eval == -0.3


class TestGetClaraCommentary:
    @pytest.mark.asyncio
    async def test_returns_commentary_and_mood(self):
        mock_llm = MagicMock(return_value='{"commentary": "Nice move!", "mood": "happy"}')

        with (
            patch("mypalclara.core.llm.make_llm", return_value=mock_llm),
            patch.dict(os.environ, {"GAME_EVENT_MEMORIES": "false"}),
        ):
            request = GameEventRequest(
                event_type="clara_move",
                game_type="checkers",
                state_summary="You're winning.",
                user_id="user-1",
                position_eval=0.5,
            )
            result = await get_clara_commentary(request, "Test personality text")

            assert result["commentary"] == "Nice move!"
            assert result["mood"] == "happy"

    @pytest.mark.asyncio
    async def test_fallback_on_llm_error(self):
        mock_llm = MagicMock(side_effect=Exception("LLM failed"))

        with (
            patch("mypalclara.core.llm.make_llm", return_value=mock_llm),
            patch.dict(os.environ, {"GAME_EVENT_MEMORIES": "false"}),
        ):
            request = GameEventRequest(
                event_type="clara_move",
                game_type="checkers",
                state_summary="test",
                user_id="user-1",
            )
            result = await get_clara_commentary(request, "Personality")

            assert result["mood"] in ("neutral", "idle")
