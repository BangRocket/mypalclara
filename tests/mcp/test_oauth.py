"""Tests for MCP OAuth 2.1 + PKCE support."""

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest

from mypalclara.core.mcp.oauth import OAuthManager, PKCEChallenge


class TestPKCEChallenge:
    """Test PKCE challenge generation."""

    def test_generate_produces_valid_verifier(self):
        """Verifier should be URL-safe base64, at least 43 chars (32 bytes encoded)."""
        pkce = PKCEChallenge.generate()
        assert len(pkce.verifier) >= 43
        # Should be URL-safe base64 (no padding)
        assert "=" not in pkce.verifier
        assert "+" not in pkce.verifier
        assert "/" not in pkce.verifier

    def test_challenge_differs_from_verifier(self):
        """Challenge must be a SHA-256 hash of verifier, not the verifier itself."""
        pkce = PKCEChallenge.generate()
        assert pkce.challenge != pkce.verifier

    def test_challenge_is_sha256_of_verifier(self):
        """Verify the challenge is correctly derived from verifier via S256."""
        pkce = PKCEChallenge.generate()
        expected = base64.urlsafe_b64encode(hashlib.sha256(pkce.verifier.encode()).digest()).rstrip(b"=").decode()
        assert pkce.challenge == expected

    def test_method_is_s256(self):
        """PKCE method should always be S256."""
        pkce = PKCEChallenge.generate()
        assert pkce.method == "S256"

    def test_generate_produces_unique_values(self):
        """Each generation should produce unique verifier/challenge pairs."""
        a = PKCEChallenge.generate()
        b = PKCEChallenge.generate()
        assert a.verifier != b.verifier
        assert a.challenge != b.challenge


class TestOAuthFlowTracking:
    """Test OAuth state tracking (start, get pending, expiry)."""

    def test_start_flow_returns_state(self, tmp_path):
        mgr = OAuthManager(token_dir=tmp_path)
        state = mgr.start_flow(
            server_name="github",
            auth_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            client_id="client123",
            redirect_uri="http://localhost:8080/callback",
            scopes=["repo", "user"],
        )
        assert isinstance(state, str)
        assert len(state) > 20

    def test_get_pending_flow(self, tmp_path):
        mgr = OAuthManager(token_dir=tmp_path)
        state = mgr.start_flow(
            server_name="github",
            auth_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            client_id="client123",
            redirect_uri="http://localhost:8080/callback",
        )
        flow = mgr.get_pending_flow(state)
        assert flow is not None
        assert flow.server_name == "github"
        assert flow.client_id == "client123"
        assert flow.pkce.method == "S256"

    def test_get_pending_flow_unknown_state(self, tmp_path):
        mgr = OAuthManager(token_dir=tmp_path)
        assert mgr.get_pending_flow("nonexistent") is None

    def test_expired_flow_returns_none(self, tmp_path):
        mgr = OAuthManager(token_dir=tmp_path)
        state = mgr.start_flow(
            server_name="github",
            auth_url="https://auth.example.com",
            token_url="https://token.example.com",
            client_id="client123",
            redirect_uri="http://localhost/cb",
        )
        # Manually expire the flow
        flow = mgr._pending_flows[state]
        flow.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)

        assert mgr.get_pending_flow(state) is None
        # Should also be cleaned up
        assert state not in mgr._pending_flows

    def test_complete_flow_removes_it(self, tmp_path):
        mgr = OAuthManager(token_dir=tmp_path)
        state = mgr.start_flow(
            server_name="github",
            auth_url="https://auth.example.com",
            token_url="https://token.example.com",
            client_id="client123",
            redirect_uri="http://localhost/cb",
        )
        flow = mgr.complete_flow(state)
        assert flow is not None
        assert flow.server_name == "github"
        # Should be gone now
        assert mgr.get_pending_flow(state) is None


class TestTokenStorage:
    """Test token storage, retrieval, and deletion."""

    def test_store_and_get_token(self, tmp_path):
        mgr = OAuthManager(token_dir=tmp_path)
        token_data = {
            "access_token": "gho_abc123",
            "token_type": "bearer",
            "scope": "repo user",
        }
        mgr.store_token("github", token_data)
        retrieved = mgr.get_token("github")
        assert retrieved is not None
        assert retrieved["access_token"] == "gho_abc123"
        assert "stored_at" in retrieved

    def test_get_nonexistent_token(self, tmp_path):
        mgr = OAuthManager(token_dir=tmp_path)
        assert mgr.get_token("nonexistent") is None

    def test_delete_token(self, tmp_path):
        mgr = OAuthManager(token_dir=tmp_path)
        mgr.store_token("github", {"access_token": "token"})
        assert mgr.delete_token("github") is True
        assert mgr.get_token("github") is None

    def test_delete_nonexistent_token(self, tmp_path):
        mgr = OAuthManager(token_dir=tmp_path)
        assert mgr.delete_token("nonexistent") is False

    def test_has_valid_token_with_expiry(self, tmp_path):
        mgr = OAuthManager(token_dir=tmp_path)
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        mgr.store_token("github", {"access_token": "tok", "expires_at": future})
        assert mgr.has_valid_token("github") is True

    def test_has_valid_token_expired(self, tmp_path):
        mgr = OAuthManager(token_dir=tmp_path)
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        mgr.store_token("github", {"access_token": "tok", "expires_at": past})
        assert mgr.has_valid_token("github") is False

    def test_has_valid_token_no_expiry(self, tmp_path):
        mgr = OAuthManager(token_dir=tmp_path)
        mgr.store_token("github", {"access_token": "tok"})
        assert mgr.has_valid_token("github") is True


class TestAuthURLBuilding:
    """Test authorization URL construction."""

    def test_build_auth_url_includes_all_params(self, tmp_path):
        mgr = OAuthManager(token_dir=tmp_path)
        state = mgr.start_flow(
            server_name="github",
            auth_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            client_id="client123",
            redirect_uri="http://localhost:8080/callback",
            scopes=["repo", "user"],
        )
        url = mgr.build_auth_url(state)
        assert url is not None

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        assert parsed.scheme == "https"
        assert parsed.netloc == "github.com"
        assert params["response_type"] == ["code"]
        assert params["client_id"] == ["client123"]
        assert params["redirect_uri"] == ["http://localhost:8080/callback"]
        assert params["state"] == [state]
        assert params["code_challenge_method"] == ["S256"]
        assert "code_challenge" in params
        assert params["scope"] == ["repo user"]

    def test_build_auth_url_without_scopes(self, tmp_path):
        mgr = OAuthManager(token_dir=tmp_path)
        state = mgr.start_flow(
            server_name="notion",
            auth_url="https://api.notion.com/v1/oauth/authorize",
            token_url="https://api.notion.com/v1/oauth/token",
            client_id="notion_client",
            redirect_uri="http://localhost/cb",
        )
        url = mgr.build_auth_url(state)
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        assert "scope" not in params

    def test_build_auth_url_unknown_state(self, tmp_path):
        mgr = OAuthManager(token_dir=tmp_path)
        assert mgr.build_auth_url("bad_state") is None
