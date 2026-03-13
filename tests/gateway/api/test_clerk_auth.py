"""Tests for Clerk JWT verification."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from mypalclara.gateway.api.clerk_auth import (
    ClerkJWKSCache,
    _get_trusted_issuer,
    verify_clerk_jwt,
)

# ---------------------------------------------------------------------------
# Fixtures: RSA key pair for signing test JWTs
# ---------------------------------------------------------------------------


@pytest.fixture()
def rsa_keypair():
    """Generate a fresh RSA key pair for test JWT signing."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    return private_key, public_key


@pytest.fixture()
def jwks_response(rsa_keypair):
    """Build a JWKS JSON response containing the test public key."""
    _, public_key = rsa_keypair
    # Export public key to JWK format
    public_numbers = public_key.public_numbers()

    def _int_to_base64url(n: int, length: int) -> str:
        return pyjwt.utils.base64url_encode(n.to_bytes(length, byteorder="big")).decode()

    jwk = {
        "kty": "RSA",
        "kid": "test-key-1",
        "use": "sig",
        "alg": "RS256",
        "n": _int_to_base64url(public_numbers.n, 256),
        "e": _int_to_base64url(public_numbers.e, 3),
    }
    return {"keys": [jwk]}


def _make_token(private_key, claims: dict | None = None, headers: dict | None = None) -> str:
    """Sign a JWT with the test private key."""
    default_claims = {
        "sub": "user_clerk_123",
        "iss": "https://test.clerk.accounts.dev",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
        "name": "Test User",
        "email": "test@example.com",
    }
    if claims:
        default_claims.update(claims)

    default_headers = {"kid": "test-key-1"}
    if headers:
        default_headers.update(headers)

    return pyjwt.encode(
        default_claims,
        private_key,
        algorithm="RS256",
        headers=default_headers,
    )


# ---------------------------------------------------------------------------
# Tests: verify_clerk_jwt
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_authorization_header():
    """Missing Authorization header raises 401."""
    with pytest.raises(HTTPException) as exc_info:
        await verify_clerk_jwt(None)
    assert exc_info.value.status_code == 401
    assert "Missing" in exc_info.value.detail


@pytest.mark.asyncio
async def test_non_bearer_authorization():
    """Authorization header without Bearer prefix raises 401."""
    with pytest.raises(HTTPException) as exc_info:
        await verify_clerk_jwt("Basic abc123")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_malformed_token():
    """Completely invalid token string raises 401."""
    with pytest.raises(HTTPException) as exc_info:
        await verify_clerk_jwt("Bearer not-a-jwt")
    assert exc_info.value.status_code == 401
    assert "Malformed" in exc_info.value.detail


@pytest.mark.asyncio
async def test_token_missing_kid():
    """Token without kid in header raises 401."""
    # Craft a token with no kid
    token = pyjwt.encode(
        {"sub": "user_123", "iss": "https://test.clerk.accounts.dev", "exp": int(time.time()) + 3600},
        "secret",
        algorithm="HS256",
        # HS256 tokens don't have kid by default
    )
    with pytest.raises(HTTPException) as exc_info:
        await verify_clerk_jwt(f"Bearer {token}")
    assert exc_info.value.status_code == 401
    assert "kid" in exc_info.value.detail


def _mock_jwks_client(jwks_response):
    """Create a mock httpx.AsyncClient that returns the JWKS response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = jwks_response

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


@pytest.mark.asyncio
async def test_valid_token_returns_claims(rsa_keypair, jwks_response, monkeypatch):
    """Valid token with mocked JWKS returns decoded claims."""
    private_key, _ = rsa_keypair
    token = _make_token(private_key)

    mock_client = _mock_jwks_client(jwks_response)
    monkeypatch.setenv("CLERK_ISSUER_URL", "https://test.clerk.accounts.dev")

    with patch("mypalclara.gateway.api.clerk_auth._cache", new=ClerkJWKSCache()):
        with patch("httpx.AsyncClient", return_value=mock_client):
            claims = await verify_clerk_jwt(f"Bearer {token}")

    assert claims["sub"] == "user_clerk_123"
    assert claims["email"] == "test@example.com"
    assert claims["name"] == "Test User"


@pytest.mark.asyncio
async def test_expired_token_raises_401(rsa_keypair, jwks_response, monkeypatch):
    """Expired token raises 401 even with valid signature."""
    private_key, _ = rsa_keypair
    token = _make_token(private_key, claims={"exp": int(time.time()) - 3600})

    mock_client = _mock_jwks_client(jwks_response)
    monkeypatch.setenv("CLERK_ISSUER_URL", "https://test.clerk.accounts.dev")

    with patch("mypalclara.gateway.api.clerk_auth._cache", new=ClerkJWKSCache()):
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(HTTPException) as exc_info:
                await verify_clerk_jwt(f"Bearer {token}")

    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail


@pytest.mark.asyncio
async def test_jwks_fetch_failure_raises_503(rsa_keypair, monkeypatch):
    """JWKS endpoint failure raises 503."""
    private_key, _ = rsa_keypair
    token = _make_token(private_key)
    monkeypatch.setenv("CLERK_ISSUER_URL", "https://test.clerk.accounts.dev")

    with patch("mypalclara.gateway.api.clerk_auth._cache", new=ClerkJWKSCache()):
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("connection refused")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(HTTPException) as exc_info:
                await verify_clerk_jwt(f"Bearer {token}")

    assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# Tests: ClerkJWKSCache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_is_stale_after_ttl():
    """Cache reports stale after TTL expires."""
    cache = ClerkJWKSCache()
    assert cache.is_stale  # Never fetched

    # Simulate a fetch
    cache._fetched_at = time.monotonic()
    assert not cache.is_stale

    # Simulate TTL expiry
    cache._fetched_at = time.monotonic() - 3601
    assert cache.is_stale


# ---------------------------------------------------------------------------
# Tests: _get_trusted_issuer (issuer validation)
# ---------------------------------------------------------------------------


def test_configured_issuer_matches(monkeypatch):
    """When CLERK_ISSUER_URL is set, matching issuer is accepted."""
    monkeypatch.setenv("CLERK_ISSUER_URL", "https://myapp.clerk.accounts.dev")
    result = _get_trusted_issuer("https://myapp.clerk.accounts.dev")
    assert result == "https://myapp.clerk.accounts.dev"


def test_configured_issuer_trailing_slash_normalization(monkeypatch):
    """Trailing slashes are normalized when comparing issuers."""
    monkeypatch.setenv("CLERK_ISSUER_URL", "https://myapp.clerk.accounts.dev/")
    result = _get_trusted_issuer("https://myapp.clerk.accounts.dev")
    assert result == "https://myapp.clerk.accounts.dev"


def test_configured_issuer_mismatch_raises_401(monkeypatch):
    """When CLERK_ISSUER_URL is set, non-matching issuer raises 401."""
    monkeypatch.setenv("CLERK_ISSUER_URL", "https://myapp.clerk.accounts.dev")
    with pytest.raises(HTTPException) as exc_info:
        _get_trusted_issuer("https://evil.example.com")
    assert exc_info.value.status_code == 401
    assert "issuer mismatch" in exc_info.value.detail


def test_configured_issuer_rejects_attacker_domain(monkeypatch):
    """Attacker-controlled issuer is rejected even if it ends with .clerk.accounts.dev."""
    monkeypatch.setenv("CLERK_ISSUER_URL", "https://real-app.clerk.accounts.dev")
    with pytest.raises(HTTPException) as exc_info:
        _get_trusted_issuer("https://fake-app.clerk.accounts.dev")
    assert exc_info.value.status_code == 401


def test_fallback_accepts_valid_clerk_domain(monkeypatch):
    """Without CLERK_ISSUER_URL, valid .clerk.accounts.dev domain is accepted."""
    monkeypatch.delenv("CLERK_ISSUER_URL", raising=False)
    result = _get_trusted_issuer("https://myapp.clerk.accounts.dev")
    assert result == "https://myapp.clerk.accounts.dev"


def test_fallback_rejects_non_clerk_domain(monkeypatch):
    """Without CLERK_ISSUER_URL, non-Clerk domain is rejected."""
    monkeypatch.delenv("CLERK_ISSUER_URL", raising=False)
    with pytest.raises(HTTPException) as exc_info:
        _get_trusted_issuer("https://evil.example.com")
    assert exc_info.value.status_code == 401
    assert "not a trusted Clerk domain" in exc_info.value.detail


def test_fallback_rejects_http_issuer(monkeypatch):
    """Without CLERK_ISSUER_URL, http:// (non-TLS) issuer is rejected."""
    monkeypatch.delenv("CLERK_ISSUER_URL", raising=False)
    with pytest.raises(HTTPException) as exc_info:
        _get_trusted_issuer("http://myapp.clerk.accounts.dev")
    assert exc_info.value.status_code == 401


def test_fallback_rejects_subdomain_spoofing(monkeypatch):
    """Without CLERK_ISSUER_URL, attacker domain mimicking suffix is rejected."""
    monkeypatch.delenv("CLERK_ISSUER_URL", raising=False)
    # "evil-clerk.accounts.dev" does NOT end with ".clerk.accounts.dev"
    with pytest.raises(HTTPException) as exc_info:
        _get_trusted_issuer("https://evil-clerk.accounts.dev")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_attacker_issuer_rejected_before_jwks_fetch(rsa_keypair, monkeypatch):
    """Token with attacker-controlled issuer is rejected before any JWKS fetch."""
    private_key, _ = rsa_keypair
    token = _make_token(private_key, claims={"iss": "https://evil.example.com"})
    monkeypatch.setenv("CLERK_ISSUER_URL", "https://myapp.clerk.accounts.dev")

    with patch("mypalclara.gateway.api.clerk_auth._cache", new=ClerkJWKSCache()) as cache:
        with patch("httpx.AsyncClient") as mock_client_cls:
            with pytest.raises(HTTPException) as exc_info:
                await verify_clerk_jwt(f"Bearer {token}")

            # JWKS endpoint should never have been called
            mock_client_cls.assert_not_called()

    assert exc_info.value.status_code == 401


