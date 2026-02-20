"""Tests for the game auth redirect endpoint."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from mypalclara.web.app import create_app

    app = create_app()
    return TestClient(app, follow_redirects=False)


class TestGameRedirect:
    def test_redirects_authenticated_user(self, client):
        """Authenticated user should get redirected with a JWT."""
        from mypalclara.db.models import CanonicalUser
        from mypalclara.web.auth.dependencies import get_current_user

        mock_user = CanonicalUser(
            id="test-user-123",
            display_name="Joshua",
            avatar_url="https://example.com/avatar.png",
            status="active",
        )
        client.app.dependency_overrides[get_current_user] = lambda: mock_user
        try:
            resp = client.get(
                "/auth/game-redirect?redirect_uri=https://games.mypalclara.com/auth/callback",
                cookies={"access_token": "fake-valid-token"},
            )
        finally:
            client.app.dependency_overrides.pop(get_current_user, None)

        assert resp.status_code == 302
        location = resp.headers["location"]
        assert "games.mypalclara.com/auth/callback" in location
        assert "token=" in location

    def test_rejects_invalid_redirect_uri(self, client):
        """Should reject redirect URIs not on games.mypalclara.com."""
        from mypalclara.db.models import CanonicalUser
        from mypalclara.web.auth.dependencies import get_current_user

        mock_user = CanonicalUser(
            id="test-user-123",
            display_name="Joshua",
            status="active",
        )
        client.app.dependency_overrides[get_current_user] = lambda: mock_user
        try:
            resp = client.get(
                "/auth/game-redirect?redirect_uri=https://evil.com/steal",
                cookies={"access_token": "fake-valid-token"},
            )
        finally:
            client.app.dependency_overrides.pop(get_current_user, None)

        assert resp.status_code == 400
