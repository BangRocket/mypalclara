"""Clerk JWT verification for the gateway API.

Validates JWTs issued by Clerk (https://clerk.com) using their JWKS endpoint.
Clerk publishes RS256 public keys at https://{domain}/.well-known/jwks.json.
"""

from __future__ import annotations

import logging
import time

import httpx
import jwt
from fastapi import HTTPException, status

logger = logging.getLogger("gateway.api.clerk_auth")

# Cache JWKS keys for 1 hour (Clerk rotates keys infrequently)
_JWKS_CACHE_TTL_SECONDS = 3600


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

    async def get_key(self, kid: str, issuer: str) -> jwt.PyJWK:
        """Get the public key for the given kid.

        Fetches from JWKS endpoint if cache is stale or kid is unknown.
        Raises HTTPException(503) if the JWKS endpoint is unreachable.
        """
        if kid not in self._keys or self.is_stale:
            await self._refresh(issuer)

        # After refresh, try one more time for unknown kid
        if kid not in self._keys:
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
    issuer = unverified_claims.get("iss")

    if not kid or not issuer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT missing kid or iss",
        )

    # Fetch the signing key
    signing_key = await _cache.get_key(kid, issuer)

    # Verify signature, expiry, and issuer
    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            issuer=issuer,
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
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT",
        ) from exc

    return claims
