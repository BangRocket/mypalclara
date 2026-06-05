# Client Trim — Sub-plan 3: Client Rewire (master plan)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Master plan: the
> `EngineApiClient` foundation is fully specified; each rewire group is boundary-test-driven
> (forbid the engine import → rewire its sites → green). Build foundation first, then groups
> simplest-first.

**Executes in:** `/Volumes/Storage/Code/mypalclara` (the client repo). The engine endpoints these
call live in `mypal-engine` (already built); local dev now requires a running engine on
`CLARA_GATEWAY_API_URL`.

**Goal:** Replace the ~50 in-process engine calls in the adapters (`get_mcp_manager`, `SessionLocal`
+ models, `ClaraMemory`, `get_backup_service`, `get_sandbox_manager`, `channel_config`, inline
guild-config) with calls to an `EngineApiClient` that hits the engine's HTTP API. This is what makes
the Sub-plan 4 cut possible — afterwards no adapter imports an engine package.

**Architecture:** One async httpx-based `EngineApiClient` in `mypalclara/client_common/` (engine-free;
it speaks HTTP, imports no engine code). It reads `CLARA_GATEWAY_API_URL` (default
`http://127.0.0.1:18790`) + `CLARA_GATEWAY_SECRET`, sends `X-Gateway-Secret`, and exposes one method
per engine endpoint built in Sub-plan 2. Adapter call sites swap in-process calls for client methods.

**Tech Stack:** httpx 0.28 (incl. `MockTransport` for tests, no new dep), pytest asyncio, AST arch test.

---

## Task 0: `EngineApiClient` foundation (fully specified)

**Files:**
- Create: `mypalclara/client_common/engine_client.py`
- Test: `tests/client_common/test_engine_client.py`

**Behavior:** base_url from `CLARA_GATEWAY_API_URL` (default `http://127.0.0.1:18790`), secret from
`CLARA_GATEWAY_SECRET`; every request carries `X-Gateway-Secret`. Methods return parsed JSON. A
`transport=` kwarg allows injecting `httpx.MockTransport` in tests.

Method ↔ endpoint map (all under `/api/v1`):

| Method | HTTP |
|---|---|
| `backup_run(databases=None)` | POST /backup/run |
| `backup_status()` | GET /backup/status |
| `sandbox_status()` | GET /sandbox/status |
| `get_channel_mode(channel_id)` | GET /channels/{id}/mode |
| `set_channel_mode(channel_id, guild_id, mode, configured_by=None)` | PUT /channels/{id}/mode |
| `list_guild_channels(guild_id)` | GET /guilds/{id}/channels |
| `get_guild_config(guild_id)` | GET /guilds/{id}/config |
| `update_guild_config(guild_id, **fields)` | PUT /guilds/{id}/config |
| `list_email_accounts(user_id)` | GET /email-accounts?user_id= |
| `resolve_link(prefixed_user_id)` | GET /users/links/{prefixed} |
| `list_user_links(canonical_id)` | GET /users/{id}/links |
| `create_link(**body)` | POST /users/links |
| `delete_link(prefixed_user_id)` | DELETE /users/links/{prefixed} |
| `mcp_list_servers()` | GET /mcp/servers |
| `mcp_server_status(name)` | GET /mcp/servers/{name}/status |
| `mcp_list_tools()` | GET /mcp/tools |
| `mcp_lifecycle(name, action)` | POST /mcp/servers/{name}/{action} |
| `mcp_reload()` | POST /mcp/reload |
| `mcp_search(query, page=1, page_size=10)` | GET /mcp/search |
| `mcp_install(source, name=None, installed_by=None)` | POST /mcp/install |
| `mcp_uninstall(name)` | DELETE /mcp/servers/{name} |

- [ ] **Step 1: Failing test** (uses `httpx.MockTransport` to assert URL/headers/payload + parse)

```python
# tests/client_common/test_engine_client.py
import httpx
import pytest

from mypalclara.client_common.engine_client import EngineApiClient


def _transport(captured):
    def handler(request):
        captured["request"] = request
        if request.url.path == "/api/v1/backup/status":
            return httpx.Response(200, json={"configured": True})
        if request.url.path == "/api/v1/channels/c1/mode":
            return httpx.Response(200, json={"mode": "active"})
        return httpx.Response(200, json={"ok": True})

    return httpx.MockTransport(handler)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CLARA_GATEWAY_SECRET", "s3cr3t")
    monkeypatch.setenv("CLARA_GATEWAY_API_URL", "http://engine:18790")
    captured = {}
    c = EngineApiClient(transport=_transport(captured))
    c._captured = captured  # test convenience
    return c


async def test_sends_secret_header_and_parses(client):
    data = await client.backup_status()
    assert data == {"configured": True}
    req = client._captured["request"]
    assert req.headers["X-Gateway-Secret"] == "s3cr3t"
    assert str(req.url).startswith("http://engine:18790")


async def test_put_channel_mode_payload(client):
    data = await client.set_channel_mode("c1", "g1", "active", configured_by="u1")
    assert data == {"mode": "active"}
    req = client._captured["request"]
    assert req.method == "PUT" and req.url.path == "/api/v1/channels/c1/mode"


async def test_mcp_lifecycle_path(client):
    await client.mcp_lifecycle("s1", "restart")
    assert client._captured["request"].url.path == "/api/v1/mcp/servers/s1/restart"
```

- [ ] **Step 2: Run — expect FAIL (ImportError).**

- [ ] **Step 3: Implement `engine_client.py`** (httpx.AsyncClient, secret header, one method per row)

```python
"""HTTP client the adapters use to reach the engine API (engine-import-free)."""

from __future__ import annotations

import os
from typing import Any

import httpx

_DEFAULT_BASE = "http://127.0.0.1:18790"


class EngineApiClient:
    def __init__(self, base_url: str | None = None, secret: str | None = None, transport=None):
        self._base = (base_url or os.getenv("CLARA_GATEWAY_API_URL", _DEFAULT_BASE)).rstrip("/")
        self._secret = secret or os.getenv("CLARA_GATEWAY_SECRET", "")
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        headers = {"X-Gateway-Secret": self._secret}
        return httpx.AsyncClient(base_url=self._base, headers=headers, transport=self._transport, timeout=30.0)

    async def _request(self, method: str, path: str, **kw) -> Any:
        async with self._client() as c:
            resp = await c.request(method, path, **kw)
            resp.raise_for_status()
            return resp.json()

    # backup
    async def backup_run(self, databases=None):
        return await self._request("POST", "/api/v1/backup/run", json={"databases": databases})

    async def backup_status(self):
        return await self._request("GET", "/api/v1/backup/status")

    # sandbox
    async def sandbox_status(self):
        return await self._request("GET", "/api/v1/sandbox/status")

    # channels
    async def get_channel_mode(self, channel_id):
        return await self._request("GET", f"/api/v1/channels/{channel_id}/mode")

    async def set_channel_mode(self, channel_id, guild_id, mode, configured_by=None):
        return await self._request(
            "PUT", f"/api/v1/channels/{channel_id}/mode",
            json={"guild_id": guild_id, "mode": mode, "configured_by": configured_by},
        )

    async def list_guild_channels(self, guild_id):
        return await self._request("GET", f"/api/v1/guilds/{guild_id}/channels")

    # guild config
    async def get_guild_config(self, guild_id):
        return await self._request("GET", f"/api/v1/guilds/{guild_id}/config")

    async def update_guild_config(self, guild_id, **fields):
        return await self._request("PUT", f"/api/v1/guilds/{guild_id}/config", json=fields)

    # email
    async def list_email_accounts(self, user_id):
        return await self._request("GET", "/api/v1/email-accounts", params={"user_id": user_id})

    # links
    async def resolve_link(self, prefixed_user_id):
        return await self._request("GET", f"/api/v1/users/links/{prefixed_user_id}")

    async def list_user_links(self, canonical_id):
        return await self._request("GET", f"/api/v1/users/{canonical_id}/links")

    async def create_link(self, **body):
        return await self._request("POST", "/api/v1/users/links", json=body)

    async def delete_link(self, prefixed_user_id):
        return await self._request("DELETE", f"/api/v1/users/links/{prefixed_user_id}")

    # mcp
    async def mcp_list_servers(self):
        return await self._request("GET", "/api/v1/mcp/servers")

    async def mcp_server_status(self, name):
        return await self._request("GET", f"/api/v1/mcp/servers/{name}/status")

    async def mcp_list_tools(self):
        return await self._request("GET", "/api/v1/mcp/tools")

    async def mcp_lifecycle(self, name, action):
        return await self._request("POST", f"/api/v1/mcp/servers/{name}/{action}")

    async def mcp_reload(self):
        return await self._request("POST", "/api/v1/mcp/reload")

    async def mcp_search(self, query, page=1, page_size=10):
        return await self._request(
            "GET", "/api/v1/mcp/search", params={"query": query, "page": page, "page_size": page_size}
        )

    async def mcp_install(self, source, name=None, installed_by=None):
        return await self._request(
            "POST", "/api/v1/mcp/install", json={"source": source, "name": name, "installed_by": installed_by}
        )

    async def mcp_uninstall(self, name):
        return await self._request("DELETE", f"/api/v1/mcp/servers/{name}")
```

- [ ] **Step 4: Run — expect PASS. Lint. Commit.**

---

## Rewire groups (boundary-test-driven, simplest-first)

For each group: (1) add the engine module(s) to a CLIENT-forbidden set in
`tests/architecture/test_engine_boundary.py`; (2) run it → FAIL (still imported); (3) rewire the
call sites to `EngineApiClient`; (4) run → PASS; (5) smoke-import the adapter module; (6) commit.

| Order | Group | Forbid from client | Sites |
|---|---|---|---|
| 1 | backup | `core.services.backup` | discord/ui/commands.py (5) |
| 2 | sandbox | `sandbox.manager` | discord/ui/commands.py (2) — also fixes broken `get_status()` |
| 3 | channels | `db.channel_config` + `ChannelConfig` | discord/ui/commands.py, channel_modes.py |
| 4 | guild-config | inline helpers → client calls | discord/ui/commands.py (5) |
| 5 | email-accounts | `EmailAccount` from db.models | discord/ui/commands.py (1) |
| 6 | identity links | `SessionLocal`, `PlatformLink`, `CanonicalUser` | cli/commands.py (~15) |
| 7 | MCP core | `core.mcp` (+ installer) | discord/ui/commands.py, cli/commands.py (~28) |

**NOT in scope this sub-plan (must precede the cut):**
- **MCP OAuth** sites (discord/ui/commands.py:680–902) — their endpoints are deferred (Sub-plan 2
  follow-up). They keep direct `core.mcp.oauth`/`load_server_config` calls until then; the boundary
  test allowlists exactly these files for `core.mcp` until the OAuth endpoints + rewire land.
- **`ClaraMemory`** (discord/ui/commands.py) — verify the existing `/api/v1/memories` endpoints cover
  the call before rewiring; if not, that's a small Sub-plan 2 addition. Tracked as a risk.

## Definition of done (Sub-plan 3)

`EngineApiClient` exists + tested. Every adapter call site in the table is rewired. The architecture
test forbids each rewired engine module from the client (except the explicitly-allowlisted MCP-OAuth
files). Adapters import no engine package except the temporary OAuth allowlist. Client modules still
import-smoke clean. (Local dev now needs a running engine — expected.)
