"""Fernet symmetric encryption for per-user secrets at rest."""

from __future__ import annotations

import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken


@lru_cache(maxsize=1)
def get_fernet() -> Fernet:
    key = os.environ.get("SECRETS_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("SECRETS_ENCRYPTION_KEY env var is required")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(plaintext: str) -> bytes:
    return get_fernet().encrypt(plaintext.encode("utf-8"))


def decrypt_secret(ciphertext: bytes) -> str:
    try:
        return get_fernet().decrypt(ciphertext).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Decryption failed — ciphertext tampered or key mismatch") from exc
