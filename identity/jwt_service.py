"""JWT signing and verification."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from identity.config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET


def encode(canonical_user_id: str, name: str = "") -> str:
    payload = {
        "sub": canonical_user_id,
        "name": name,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
