"""Shared Fernet credential encryption for secret-bearing integrations.

Uses CREDENTIAL_ENCRYPTION_KEY if set, falling back to EMAIL_ENCRYPTION_KEY
for backward compatibility with the email integration.

The key is operator-provided via environment; nothing is auto-generated.
Generate one with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken

from mypalclara.config.logging import get_logger

logger = get_logger("core.credentials")

_fernet: Fernet | None = None


def _get_key() -> str | None:
    """Resolve the encryption key from env, preferring CREDENTIAL_ENCRYPTION_KEY."""
    return os.getenv("CREDENTIAL_ENCRYPTION_KEY") or os.getenv("EMAIL_ENCRYPTION_KEY")


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = _get_key()
        if not key:
            raise ValueError(
                "CREDENTIAL_ENCRYPTION_KEY (or EMAIL_ENCRYPTION_KEY) environment "
                "variable is required to store encrypted credentials."
            )
        _fernet = Fernet(key.encode())
    return _fernet


def encrypt_credential(plaintext: str) -> str:
    """Encrypt a credential for database storage."""
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_credential(ciphertext: str) -> str:
    """Decrypt a credential from database storage.

    Raises:
        ValueError: If decryption fails (key mismatch or tampered ciphertext).
    """
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:
        logger.error("Failed to decrypt credential — key may have changed")
        raise ValueError("Failed to decrypt credential") from e


def is_encryption_configured() -> bool:
    """True if an encryption key is available in the environment."""
    return bool(_get_key())


def reset_cache() -> None:
    """Clear the cached Fernet instance (test use only)."""
    global _fernet
    _fernet = None
