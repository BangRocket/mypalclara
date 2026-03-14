"""Clerk JWT verification for the gateway API.

Validates JWTs issued by Clerk (https://clerk.com) using their JWKS endpoint.
Clerk publishes RS256 public keys at https://{domain}/.well-known/jwks.json.

Security: The trusted issuer is read from CLERK_ISSUER_URL env var. If unset,
the token's issuer must end with `.clerk.accounts.dev` as a safety net. The
issuer from the *unverified* token is never used to construct the JWKS URL.
"""

from __future__ import annotations

import logging
import os
import time

import httpx
import jwt
from fastapi import HTTPException, status

logger = logging.getLogger("gateway.api.clerk_auth")

_CLERK_DOMAIN_SUFFIX = ".clerk.accounts.dev"

# Cache JWKS keys for 1 hour (Clerk rotates keys infrequently)
_JWKS_CACHE_TTL_SECONDS = 3600
# Minimum interval between JWKS refreshes to prevent abuse via unknown kid values
_JWKS_MIN_REFRESH_INTERVAL = 30


class ClerkJWKSCache:
    """Fetches and caches Clerk's JWKS public keys.

    Keys are cached for 1 hour. On cache miss or unknown kid,
    the cache is refreshed from the JWKS endpoint.
    """

    def __init__(self) -> None:
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at: float = 0.0

    @property
    def is_stale(self) -> bool:
        return (time.monotonic() - self._fetched_at) > _JWKS_CACHE_TTL_SECONDS

    @property
    def _recently_refreshed(self) -> bool:
        return (time.monotonic() - self._fetched_at) < _JWKS_MIN_REFRESH_INTERVAL

    async def get_key(self, kid: str, issuer: str) -> jwt.PyJWK:
        """Get the public key for the given kid.

        Fetches from JWKS endpoint if cache is stale or kid is unknown.
        Raises HTTPException(503) if the JWKS endpoint is unreachable.
        """
        if kid not in self._keys or self.is_stale:
            if not self._recently_refreshed:
                await self._refresh(issuer)
            if kid not in self._keys and not self._recently_refreshed:
                # Key rotation race: one more try
                await self._refresh(issuer)

        key = self._keys.get(kid)
        if key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT signing key not found in JWKS",
            )
        return key

    async def _refresh(self, issuer: str) -> None:
        """Fetch JWKS from Clerk's well-known endpoint."""
        jwks_url = f"{issuer}/.well-known/jwks.json"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(jwks_url)
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Failed to fetch Clerk JWKS from %s: %s", jwks_url, exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to fetch Clerk signing keys",
            ) from exc

        jwks_data = resp.json()
        jwk_set = jwt.PyJWKSet.from_dict(jwks_data)
        self._keys = {k.key_id: k for k in jwk_set.keys}
        self._fetched_at = time.monotonic()
        logger.debug("Refreshed Clerk JWKS cache: %d keys", len(self._keys))


# Module-level singleton
_cache = ClerkJWKSCache()


def _get_trusted_issuer(token_issuer: str) -> str:
    """Return the trusted issuer URL, validating against config or domain suffix.

    If CLERK_ISSUER_URL is set, the token's issuer must match it exactly.
    Otherwise, the token's issuer must end with `.clerk.accounts.dev`.

    This prevents an attacker from crafting a token with an arbitrary issuer
    that points to their own JWKS server.

    Returns:
        The trusted issuer URL to use for JWKS fetching.

    Raises:
        HTTPException(401): If the token's issuer is not trusted.
    """
    configured = os.environ.get("CLERK_ISSUER_URL")
    if configured:
        # Strip trailing slash for consistent comparison
        configured = configured.rstrip("/")
        token_iss = token_issuer.rstrip("/")
        if token_iss != configured:
            logger.warning(
                "JWT issuer %r does not match configured CLERK_ISSUER_URL %r",
                token_issuer,
                configured,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="JWT issuer mismatch",
            )
        return configured

    # Fallback: validate the issuer domain when CLERK_ISSUER_URL is not configured
    from urllib.parse import urlparse

    parsed = urlparse(token_issuer)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith(_CLERK_DOMAIN_SUFFIX)
    ):
        logger.warning(
            "JWT issuer %r is not a trusted Clerk domain (set CLERK_ISSUER_URL to "
            "configure an explicit issuer)",
            token_issuer,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT issuer is not a trusted Clerk domain",
        )
    return token_issuer.rstrip("/")


async def verify_clerk_jwt(authorization: str) -> dict:
    """Verify a Clerk JWT from an Authorization header.

    Args:
        authorization: The full Authorization header value (e.g. "Bearer eyJ...").

    Returns:
        Decoded JWT claims dict.

    Raises:
        HTTPException(401): Missing, malformed, or invalid token.
        HTTPException(503): JWKS endpoint unreachable.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
        )

    token = authorization[len("Bearer ") :]

    # Decode header without verification to get kid and iss
    try:
        unverified_header = jwt.get_unverified_header(token)
        unverified_claims = jwt.decode(token, options={"verify_signature": False})
    except jwt.DecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed JWT",
        ) from exc

    kid = unverified_header.get("kid")
    token_issuer = unverified_claims.get("iss")

    if not kid or not token_issuer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT missing kid or iss",
        )

    # Validate issuer against trusted config BEFORE fetching JWKS
    trusted_issuer = _get_trusted_issuer(token_issuer)

    # Fetch the signing key using the TRUSTED issuer, not the token's claim
    signing_key = await _cache.get_key(kid, trusted_issuer)

    # Verify signature, expiry, issuer, and audience against trusted values
    decode_kwargs: dict = {
        "algorithms": ["RS256"],
        "issuer": trusted_issuer,
    }
    clerk_audience = os.environ.get("CLERK_AUDIENCE")
    if clerk_audience:
        decode_kwargs["audience"] = clerk_audience

    try:
        claims = jwt.decode(
            token,
            signing_key,
            **decode_kwargs,
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT has expired",
        ) from exc
    except jwt.InvalidIssuerError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT issuer mismatch",
        ) from exc
    except jwt.InvalidAudienceError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT audience mismatch",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT",
        ) from exc

    return claims
