"""Tests for the game move API endpoint."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with the game router mounted."""
    from mypalclara.web.app import create_app

    app = create_app()
    return TestClient(app)


@pytest.fixture
def game_api_key(monkeypatch):
    """Set the game API key for auth."""
    monkeypatch.setenv("GAME_API_KEY", "test-secret-key")


class TestGameMoveEndpoint:
    def test_returns_move_and_commentary(self, client, game_api_key):
        """Clara should return a valid move from legal_moves plus commentary."""
        payload = {
            "game_type": "blackjack",
            "game_state": {"player_hand": ["A\u2660", "7\u2665"], "dealer_hand": ["K\u2666", "?"]},
            "legal_moves": ["hit", "stand"],
            "personality": "clara",
            "user_id": "test-user-123",
            "move_history": [],
        }
        with patch("mypalclara.adapters.game.api.get_clara_move") as mock_get_move:
            mock_get_move.return_value = {
                "move": {"type": "stand"},
                "commentary": "Playing it safe, huh?",
                "mood": "smug",
            }
            resp = client.post(
                "/api/v1/game/move",
                json=payload,
                headers={"X-Game-API-Key": "test-secret-key"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["move"]["type"] in ["hit", "stand"]
        assert "commentary" in data
        assert data["mood"] in ["idle", "happy", "nervous", "smug", "surprised", "defeated"]

    def test_rejects_missing_api_key(self, client, game_api_key):
        """Requests without API key should be rejected."""
        payload = {
            "game_type": "blackjack",
            "game_state": {},
            "legal_moves": ["hit", "stand"],
            "personality": "clara",
            "user_id": "test-user-123",
            "move_history": [],
        }
        resp = client.post("/api/v1/game/move", json=payload)
        assert resp.status_code == 401

    def test_rejects_invalid_api_key(self, client, game_api_key):
        """Requests with wrong API key should be rejected."""
        payload = {
            "game_type": "blackjack",
            "game_state": {},
            "legal_moves": ["hit", "stand"],
            "personality": "clara",
            "user_id": "test-user-123",
            "move_history": [],
        }
        resp = client.post(
            "/api/v1/game/move",
            json=payload,
            headers={"X-Game-API-Key": "wrong-key"},
        )
        assert resp.status_code == 401

    def test_validates_personality(self, client, game_api_key):
        """Only known personalities should be accepted."""
        payload = {
            "game_type": "blackjack",
            "game_state": {},
            "legal_moves": ["hit", "stand"],
            "personality": "nonexistent",
            "user_id": "test-user-123",
            "move_history": [],
        }
        resp = client.post(
            "/api/v1/game/move",
            json=payload,
            headers={"X-Game-API-Key": "test-secret-key"},
        )
        assert resp.status_code == 422
