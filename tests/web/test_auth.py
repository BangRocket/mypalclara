"""Tests for web auth JWT session management."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mypalclara.web.auth.session import create_access_token, decode_access_token, hash_token


@pytest.fixture(autouse=True)
def _mock_config():
    """Mock the web config for all tests in this module."""
    with patch("mypalclara.web.auth.session.get_web_config") as mock:
        cfg = mock.return_value
        cfg.secret_key = "test-secret-key"
        cfg.jwt_algorithm = "HS256"
        cfg.jwt_expire_minutes = 60
        yield cfg


class TestJWT:
    """Tests for JWT token creation and decoding."""

    def test_create_and_decode_token(self):
        """Token round-trips correctly."""
        token = create_access_token(canonical_user_id="user-123")
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert "exp" in payload

    def test_decode_with_wrong_secret_fails(self, _mock_config):
        """Decoding with wrong secret returns None."""
        token = create_access_token(canonical_user_id="user-123")
        # Change the secret before decoding
        _mock_config.secret_key = "wrong-secret"
        result = decode_access_token(token)
        assert result is None

    def test_expired_token_returns_none(self, _mock_config):
        """Expired token returns None on decode."""
        _mock_config.jwt_expire_minutes = -1  # Already expired
        token = create_access_token(canonical_user_id="user-123")
        _mock_config.jwt_expire_minutes = 60  # Restore for decode
        result = decode_access_token(token)
        assert result is None

    def test_extra_claims(self):
        """Extra claims are included in the token."""
        token = create_access_token(
            canonical_user_id="user-123",
            extra_claims={"role": "admin"},
        )
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["role"] == "admin"

    def test_hash_token_deterministic(self):
        """Hashing the same token twice gives the same result."""
        h1 = hash_token("my-token")
        h2 = hash_token("my-token")
        assert h1 == h2

    def test_hash_token_different_inputs(self):
        """Different tokens produce different hashes."""
        h1 = hash_token("token-a")
        h2 = hash_token("token-b")
        assert h1 != h2
