"""Credential encryption for email account passwords.

Delegates to mypalclara.core.credentials for shared Fernet-based encryption.
CREDENTIAL_ENCRYPTION_KEY is preferred; EMAIL_ENCRYPTION_KEY is kept as a
fallback for backward compatibility.
"""

from __future__ import annotations

from mypalclara.core.credentials import (
    decrypt_credential,
    encrypt_credential,
    is_encryption_configured,
)

__all__ = ["decrypt_credential", "encrypt_credential", "is_encryption_configured"]
