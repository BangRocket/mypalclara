# Client Trim — Sub-plan 2: Engine API Gap-Fill (master plan)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. This is a MASTER plan
> for a multi-subsystem effort: it fully specifies the shared foundation + one worked group
> (backup), gives precise contracts for the other groups, and defers the largest group (MCP) to its
> own detailed plan. Build groups one at a time, simplest-first.

**Executes in:** `/Volumes/Storage/Code/mypal-engine` (the canonical engine repo). All paths below
are relative to that repo. (This plan doc lives in `mypalclara/docs` to keep the Phase 2c narrative
together, but the code lands in `mypal-engine`.)

**Goal:** Add the HTTP API endpoints the client currently bypasses via in-process engine calls, so
that Sub-plan 3 can rewire the adapters to call the engine over HTTP instead of importing
`core`/`db`/`sandbox` directly. Engine keeps owning the DB.

**Architecture:** Each group is a FastAPI router under `mypalclara/gateway/api/`, registered in
`app.py`, gated by a new `require_gateway_secret` dependency (trusted internal caller — adapters
already hold `CLARA_GATEWAY_SECRET`). User-scoped groups additionally use the existing
`get_approved_user` (X-Canonical-User-Id). Backing logic is the existing engine accessors —
endpoints are thin wrappers, no business logic moves.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, pytest + FastAPI `TestClient`.

---

## Why a master plan (scope)

The exploration found **7 independent endpoint groups** backing ~50 client call sites, almost all in
`mypalclara/adapters/discord/ui/commands.py` (+ `cli/commands.py` for identity links). They share
one pattern but are otherwise independent. Building them as one giant plan would be unreviewable;
instead this plan locks the shared foundation + contracts, and each group is built/verified on its
own. **MCP (group 7, ~36 sites) gets its own detailed plan** — it is as large as all others combined.

## Build order (simplest → hardest)

1. **Foundation** — `require_gateway_secret` dependency (this plan, Task 0)
2. **backup** — worked template in this plan (Task 1)
3. **sandbox status** — trivial (contract below)
4. **channel-config** — DB read/write
5. **guild-config** — DB read/write
6. **email-accounts** — user-scoped DB read
7. **users/links extension** — CLI identity linking (extend existing `users` router)
8. **mcp** — separate detailed plan: `...-phase2c-2g-mcp.md`

---

## Task 0: Shared foundation — `require_gateway_secret`

**Files:**
- Modify: `mypalclara/gateway/api/auth.py`
- Test: `tests/gateway/api/test_auth_gateway_secret.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/gateway/api/test_auth_gateway_secret.py
import os
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from mypalclara.gateway.api.auth import require_gateway_secret


@pytest.fixture
def app_client(monkeypatch):
    monkeypatch.setenv("CLARA_GATEWAY_SECRET", "s3cr3t")
    app = FastAPI()

    @app.get("/internal/ping")
    async def ping(_: bool = Depends(require_gateway_secret)):
        return {"ok": True}

    return TestClient(app)


def test_rejects_missing_secret(app_client):
    assert app_client.get("/internal/ping").status_code == 401


def test_rejects_wrong_secret(app_client):
    r = app_client.get("/internal/ping", headers={"X-Gateway-Secret": "nope"})
    assert r.status_code == 401


def test_accepts_correct_secret(app_client):
    r = app_client.get("/internal/ping", headers={"X-Gateway-Secret": "s3cr3t"})
    assert r.status_code == 200 and r.json() == {"ok": True}
```

- [ ] **Step 2: Run it — expect FAIL (ImportError: require_gateway_secret)**

Run: `poetry run pytest tests/gateway/api/test_auth_gateway_secret.py -v`

- [ ] **Step 3: Implement the dependency in `auth.py`**

Append to `mypalclara/gateway/api/auth.py`:

```python
def require_gateway_secret(
    x_gateway_secret: str | None = Header(None),
) -> bool:
    """Authorize a trusted internal caller (an adapter) via the shared secret.

    Management endpoints (MCP, channel/guild config, backup, sandbox) are not
    user-scoped; they authorize on CLARA_GATEWAY_SECRET alone. Raises 401 if the
    secret is unset on the server or does not match.
    """
    expected = os.getenv("CLARA_GATEWAY_SECRET")
    if not expected or x_gateway_secret != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing gateway secret",
        )
    return True
```

- [ ] **Step 4: Run the test — expect PASS. Commit.**

```bash
git add mypalclara/gateway/api/auth.py tests/gateway/api/test_auth_gateway_secret.py
git commit -m "feat(api): add require_gateway_secret dep for internal endpoints"
```

---

## Task 1: backup endpoints (worked template — every later group follows this shape)

**Backing interface** (`mypalclara/core/services/backup.py`):
`get_backup_service() -> BackupService`; `await service.backup_now(databases: list[str] | None)
-> BackupResult`; `await service.get_status() -> dict`; `await service.list_backups() -> list`.
`BackupResult` dataclass fields: `success, message, databases_backed_up, databases_failed,
databases_skipped, timestamp, errors`.

**Contract:**
| Method | Path | Auth | Body | Returns |
|---|---|---|---|---|
| POST | `/api/v1/backup/run` | gateway-secret | `{"databases": ["clara","palace"] \| null}` | `BackupResult` as JSON |
| GET | `/api/v1/backup/status` | gateway-secret | — | status dict |

**Files:**
- Create: `mypalclara/gateway/api/backup.py`
- Modify: `mypalclara/gateway/api/app.py` (register router)
- Test: `tests/gateway/api/test_backup_api.py`

- [ ] **Step 1: Failing test** (monkeypatch `get_backup_service` to a fake; assert routing + shape)

```python
# tests/gateway/api/test_backup_api.py
import pytest
from fastapi.testclient import TestClient

from mypalclara.gateway.api.app import create_app
import mypalclara.gateway.api.backup as backup_api


class _FakeService:
    async def backup_now(self, databases=None):
        from types import SimpleNamespace
        return SimpleNamespace(
            success=True, message="ok", databases_backed_up=databases or ["clara"],
            databases_failed=[], databases_skipped=[], timestamp="2026-06-03T00:00:00", errors=[],
        )

    async def get_status(self):
        return {"configured": True, "last_backup": None}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CLARA_GATEWAY_SECRET", "s3cr3t")
    monkeypatch.setattr(backup_api, "get_backup_service", lambda: _FakeService())
    return TestClient(create_app())


def test_backup_run_requires_secret(client):
    assert client.post("/api/v1/backup/run", json={"databases": None}).status_code == 401


def test_backup_run_ok(client):
    r = client.post("/api/v1/backup/run", json={"databases": ["clara"]},
                    headers={"X-Gateway-Secret": "s3cr3t"})
    assert r.status_code == 200
    assert r.json()["success"] is True
    assert r.json()["databases_backed_up"] == ["clara"]


def test_backup_status_ok(client):
    r = client.get("/api/v1/backup/status", headers={"X-Gateway-Secret": "s3cr3t"})
    assert r.status_code == 200 and r.json()["configured"] is True
```

- [ ] **Step 2: Run — expect FAIL (no backup router / 404).**

- [ ] **Step 3: Implement `mypalclara/gateway/api/backup.py`**

```python
"""Backup management endpoints (internal, gateway-secret auth)."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from mypalclara.core.services.backup import get_backup_service
from mypalclara.gateway.api.auth import require_gateway_secret

router = APIRouter()


class BackupRunRequest(BaseModel):
    databases: list[str] | None = None


def _to_dict(result: Any) -> dict:
    if is_dataclass(result):
        return asdict(result)
    if hasattr(result, "__dict__"):
        return dict(result.__dict__)
    return dict(result)


@router.post("/run")
async def run_backup(body: BackupRunRequest, _: bool = Depends(require_gateway_secret)) -> dict:
    service = get_backup_service()
    result = await service.backup_now(databases=body.databases)
    return _to_dict(result)


@router.get("/status")
async def backup_status(_: bool = Depends(require_gateway_secret)) -> dict:
    service = get_backup_service()
    return await service.get_status()
```

- [ ] **Step 4: Register in `app.py`**

Add import `from mypalclara.gateway.api.backup import router as backup_router` and
`app.include_router(backup_router, prefix="/api/v1/backup", tags=["backup"])`.

- [ ] **Step 5: Run the test — expect PASS. Lint. Commit.**

```bash
git add mypalclara/gateway/api/backup.py mypalclara/gateway/api/app.py tests/gateway/api/test_backup_api.py
git commit -m "feat(api): backup run/status endpoints"
```

---

## Contracts for the remaining groups (each built as its own task, same shape as Task 1)

> Each: failing test → router under `mypalclara/gateway/api/<group>.py` → register in `app.py` →
> pass → commit. Backing calls are the engine accessors from the exploration; endpoints are thin
> wrappers. Auth = `require_gateway_secret` unless noted.

### Group 3 — sandbox status
Backing: `get_sandbox_manager()` (`mypalclara/sandbox/manager.py`); use `is_available()` +
`get_stats()` (NOTE: client calls a `get_status()` that does not exist on the manager — expose a
synthesized status instead and fix the client call in Sub-plan 3).
| Method | Path | Auth | Returns |
|---|---|---|---|
| GET | `/api/v1/sandbox/status` | gateway-secret | `{"available": bool, "stats": {...}}` |

### Group 4 — channel config
Backing: `mypalclara/db/channel_config.py` — `get_channel_mode(channel_id)`,
`set_channel_mode(channel_id, guild_id, mode, configured_by=None)`, `get_guild_channels(guild_id)`.
`ChannelConfig` cols: channel_id, guild_id, mode("active"|"mention"|"off"), configured_by.
| Method | Path | Auth | Body | Returns |
|---|---|---|---|---|
| GET | `/api/v1/channels/{channel_id}/mode` | gateway-secret | — | `{"mode": str}` |
| PUT | `/api/v1/channels/{channel_id}/mode` | gateway-secret | `{"guild_id","mode","configured_by"}` | `{"mode": str}` |
| GET | `/api/v1/guilds/{guild_id}/channels` | gateway-secret | — | `[{channel_id, mode}, ...]` |

### Group 5 — guild config
Backing: extract the 3 helpers currently INLINE in `discord/ui/commands.py:56–96`
(`get_guild_config`, `save_guild_config`, `get_or_create_guild_config`) into
`mypalclara/db/guild_config.py` (engine-side), then wrap. `GuildConfig` cols: guild_id,
default_tier, auto_tier_enabled, ors_enabled, ors_channel_id, ors_quiet_start, ors_quiet_end,
sandbox_mode.
| Method | Path | Auth | Body | Returns |
|---|---|---|---|---|
| GET | `/api/v1/guilds/{guild_id}/config` | gateway-secret | — | full config dict |
| PUT | `/api/v1/guilds/{guild_id}/config` | gateway-secret | partial config | updated config dict |

### Group 6 — email accounts (user-scoped)
Backing: `EmailAccount` model query by `user_id`. Auth: `get_approved_user` (X-Canonical-User-Id) —
return only the caller's accounts. (Client read site: `discord/ui/commands.py:1351`.)
| Method | Path | Auth | Returns |
|---|---|---|---|
| GET | `/api/v1/email-accounts` | user (canonical-id) | `[{id, email_address, provider_type, enabled, status, ...}]` |

### Group 7 — users/links extension (CLI identity linking)
Backing: `PlatformLink` + `CanonicalUser` (extend existing `users.py` router). Replaces the direct
DB block in `cli/commands.py` (link/list/create/unlink, ~15 sites).
| Method | Path | Auth | Body | Returns |
|---|---|---|---|---|
| GET | `/api/v1/users/links/{prefixed_user_id}` | gateway-secret | — | link + canonical user, or 404 |
| GET | `/api/v1/users/{canonical_id}/links` | gateway-secret | — | `[links]` |
| POST | `/api/v1/users/links` | gateway-secret | `{platform, platform_user_id, prefixed_user_id, display_name, canonical_user_id?}` | created link (+ creates CanonicalUser if `canonical_user_id` omitted, using `gen_uuid`) |
| DELETE | `/api/v1/users/links/{prefixed_user_id}` | gateway-secret | — | `{deleted: bool}` |

### Group 8 — MCP management → **separate detailed plan** `...-phase2c-2g-mcp.md`
Backing: `get_mcp_manager()` + `core/mcp/{models,installer,oauth}.py`. ~36 client sites covering:
list servers/status, list tools, start/stop/restart/enable/disable, install (Smithery), uninstall,
search, and the OAuth flow (start/exchange/manual-token, `load_server_config`/`save_server_config`,
`load_oauth_state`). Sized like all other groups combined → its own plan.

---

## Definition of done (Sub-plan 2)

All 7 groups exist as routers registered in `app.py`, gated by the right auth, each with passing
`TestClient` tests, in `mypal-engine`. No business logic moved except the small `guild_config`
helper extraction. The client is NOT rewired here (Sub-plan 3). After this lands, re-sync is N/A —
the engine repo is canonical and already holds it.
