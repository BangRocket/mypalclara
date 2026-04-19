"""Repository for per-user ObsidianAccount records.

Handles Fernet encryption of the API token transparently. Callers work
with plaintext tokens in the ObsidianAccountConfig dataclass; the
database always stores ciphertext.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from mypalclara.config.logging import get_logger
from mypalclara.core.credentials import decrypt_credential, encrypt_credential
from mypalclara.db.connection import get_session
from mypalclara.db.models import ObsidianAccount, utcnow

logger = get_logger("obsidian.account")


@dataclass
class ObsidianAccountConfig:
    """Plaintext view of an ObsidianAccount row."""

    user_id: str
    base_url: str
    port: int | None
    api_token: str
    verify_tls: bool = True
    enabled: bool = True
    verified_at: datetime | None = None
    last_error: str | None = None

    @property
    def endpoint(self) -> str:
        """Full URL including optional port."""
        base = self.base_url.rstrip("/")
        if self.port:
            # Insert port before any path component
            if "://" in base:
                scheme, rest = base.split("://", 1)
                if "/" in rest:
                    host, path = rest.split("/", 1)
                    host = _host_with_port(host, self.port)
                    return f"{scheme}://{host}/{path}"
                return f"{scheme}://{_host_with_port(rest, self.port)}"
            return f"{_host_with_port(base, self.port)}"
        return base


def _host_with_port(host: str, port: int) -> str:
    """Attach :port to a host if it doesn't already have one."""
    if ":" in host.split("/", 1)[0]:
        return host  # already has port
    return f"{host}:{port}"


def _row_to_config(row: ObsidianAccount) -> ObsidianAccountConfig:
    return ObsidianAccountConfig(
        user_id=row.user_id,
        base_url=row.base_url,
        port=row.port,
        api_token=decrypt_credential(row.api_token),
        verify_tls=bool(row.verify_tls),
        enabled=bool(row.enabled),
        verified_at=row.verified_at,
        last_error=row.last_error,
    )


def get_account(user_id: str) -> ObsidianAccountConfig | None:
    """Fetch a user's Obsidian config with decrypted token, or None."""
    with get_session() as db:
        row = db.query(ObsidianAccount).filter(ObsidianAccount.user_id == user_id).first()
        if not row:
            return None
        return _row_to_config(row)


def has_account(user_id: str) -> bool:
    """True if the user has an enabled, verified Obsidian account."""
    with get_session() as db:
        row = db.query(ObsidianAccount).filter(ObsidianAccount.user_id == user_id).first()
        if not row:
            return False
        return bool(row.enabled) and row.verified_at is not None


def save_account(
    *,
    user_id: str,
    base_url: str,
    api_token: str,
    port: int | None = None,
    verify_tls: bool = True,
    enabled: bool = True,
) -> ObsidianAccountConfig:
    """Upsert an ObsidianAccount for a user. Clears verified_at and last_error."""
    ciphertext = encrypt_credential(api_token)
    with get_session() as db:
        row = db.query(ObsidianAccount).filter(ObsidianAccount.user_id == user_id).first()
        if row is None:
            row = ObsidianAccount(
                user_id=user_id,
                base_url=base_url,
                port=port,
                api_token=ciphertext,
                verify_tls=verify_tls,
                enabled=enabled,
            )
            db.add(row)
        else:
            row.base_url = base_url
            row.port = port
            row.api_token = ciphertext
            row.verify_tls = verify_tls
            row.enabled = enabled
            row.verified_at = None
            row.last_error = None
            row.updated_at = utcnow()
        db.commit()
        db.refresh(row)
        return _row_to_config(row)


def delete_account(user_id: str) -> bool:
    """Remove a user's Obsidian account. Returns True if a row was deleted."""
    with get_session() as db:
        row = db.query(ObsidianAccount).filter(ObsidianAccount.user_id == user_id).first()
        if not row:
            return False
        db.delete(row)
        db.commit()
        return True


def set_verified(user_id: str) -> None:
    """Mark a user's account as successfully verified now, clearing last_error."""
    with get_session() as db:
        row = db.query(ObsidianAccount).filter(ObsidianAccount.user_id == user_id).first()
        if not row:
            return
        row.verified_at = utcnow()
        row.last_error = None
        row.updated_at = utcnow()
        db.commit()


def set_last_error(user_id: str, error: str) -> None:
    """Record a connection error for the user's account."""
    with get_session() as db:
        row = db.query(ObsidianAccount).filter(ObsidianAccount.user_id == user_id).first()
        if not row:
            return
        row.last_error = error[:2000]
        row.updated_at = utcnow()
        db.commit()
