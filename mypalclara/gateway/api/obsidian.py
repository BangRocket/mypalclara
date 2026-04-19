"""Obsidian account settings API — per-user config for the Local REST API plugin."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from mypalclara.core.obsidian import (
    ObsidianClient,
    ObsidianError,
    delete_account,
    get_account,
    save_account,
    set_last_error,
    set_verified,
)
from mypalclara.db.models import CanonicalUser
from mypalclara.gateway.api.auth import get_approved_user

router = APIRouter()


class ObsidianSettings(BaseModel):
    base_url: str = Field(..., description="e.g., https://obsidian.example.com")
    port: int | None = Field(None, ge=1, le=65535)
    api_token: str | None = Field(
        None,
        description="Bearer token for the Local REST API. Omit on update to keep existing.",
    )
    verify_tls: bool = True
    enabled: bool = True


class ObsidianSettingsView(BaseModel):
    configured: bool
    base_url: str | None = None
    port: int | None = None
    verify_tls: bool = True
    enabled: bool = True
    verified_at: str | None = None
    last_error: str | None = None
    # Never returned: api_token


def _view(user_id: str) -> ObsidianSettingsView:
    cfg = get_account(user_id)
    if not cfg:
        return ObsidianSettingsView(configured=False)
    return ObsidianSettingsView(
        configured=True,
        base_url=cfg.base_url,
        port=cfg.port,
        verify_tls=cfg.verify_tls,
        enabled=cfg.enabled,
        verified_at=cfg.verified_at.isoformat() if cfg.verified_at else None,
        last_error=cfg.last_error,
    )


@router.get("", response_model=ObsidianSettingsView)
async def get_settings(user: CanonicalUser = Depends(get_approved_user)) -> ObsidianSettingsView:
    """Return the caller's Obsidian settings (without the token)."""
    return _view(user.id)


@router.put("", response_model=ObsidianSettingsView)
async def put_settings(
    body: ObsidianSettings,
    user: CanonicalUser = Depends(get_approved_user),
) -> ObsidianSettingsView:
    """Create or update the caller's Obsidian settings.

    If `api_token` is omitted, the existing token is preserved; otherwise
    the supplied token is stored (Fernet-encrypted). Verification state is
    reset whenever settings are written.
    """
    existing = get_account(user.id)
    token = body.api_token or (existing.api_token if existing else None)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="api_token is required on first save",
        )

    save_account(
        user_id=user.id,
        base_url=body.base_url,
        api_token=token,
        port=body.port,
        verify_tls=body.verify_tls,
        enabled=body.enabled,
    )
    return _view(user.id)


@router.delete("")
async def delete_settings(user: CanonicalUser = Depends(get_approved_user)) -> dict:
    """Remove the caller's Obsidian settings."""
    removed = delete_account(user.id)
    return {"ok": True, "removed": removed}


class TestResult(BaseModel):
    ok: bool
    detail: str
    server: dict | None = None


@router.post("/test", response_model=TestResult)
async def test_connection(user: CanonicalUser = Depends(get_approved_user)) -> TestResult:
    """Attempt a status call against the configured endpoint. Records success/failure."""
    cfg = get_account(user.id)
    if not cfg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Obsidian settings configured",
        )

    client = ObsidianClient(cfg)
    try:
        info = await client.status()
    except ObsidianError as e:
        set_last_error(user.id, str(e))
        return TestResult(ok=False, detail=str(e))

    set_verified(user.id)
    return TestResult(ok=True, detail="Connected", server=info if isinstance(info, dict) else None)
