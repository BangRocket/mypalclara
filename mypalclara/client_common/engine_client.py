"""HTTP client the adapters use to reach the engine API.

Engine-import-free: this speaks HTTP to the engine's gateway API (the same API
built in mypal-engine) so adapters no longer call engine internals in-process.
Reads CLARA_GATEWAY_API_URL (default http://127.0.0.1:18790) and
CLARA_GATEWAY_SECRET, and sends the secret as X-Gateway-Secret on every request.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

_DEFAULT_BASE = "http://127.0.0.1:18790"


class EngineApiClient:
    """Thin async wrapper over the engine's /api/v1 HTTP surface."""

    def __init__(
        self,
        base_url: str | None = None,
        secret: str | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 30.0,
    ):
        self._base = (base_url or os.getenv("CLARA_GATEWAY_API_URL", _DEFAULT_BASE)).rstrip("/")
        self._secret = secret or os.getenv("CLARA_GATEWAY_SECRET", "")
        self._transport = transport
        self._timeout = timeout

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base,
            headers={"X-Gateway-Secret": self._secret},
            transport=self._transport,
            timeout=self._timeout,
        )

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        async with self._client() as client:
            resp = await client.request(method, path, **kwargs)
            resp.raise_for_status()
            return resp.json()

    # --- backup ---
    async def backup_run(self, databases: list[str] | None = None) -> Any:
        return await self._request("POST", "/api/v1/backup/run", json={"databases": databases})

    async def backup_status(self) -> Any:
        return await self._request("GET", "/api/v1/backup/status")

    async def backup_list(self, database: str | None = None, limit: int = 10) -> Any:
        params: dict = {"limit": limit}
        if database is not None:
            params["database"] = database
        return await self._request("GET", "/api/v1/backup/list", params=params)

    # --- sandbox ---
    async def sandbox_status(self) -> Any:
        return await self._request("GET", "/api/v1/sandbox/status")

    # --- channels ---
    async def get_channel_mode(self, channel_id: str) -> Any:
        return await self._request("GET", f"/api/v1/channels/{channel_id}/mode")

    async def set_channel_mode(
        self, channel_id: str, guild_id: str, mode: str, configured_by: str | None = None
    ) -> Any:
        return await self._request(
            "PUT",
            f"/api/v1/channels/{channel_id}/mode",
            json={"guild_id": guild_id, "mode": mode, "configured_by": configured_by},
        )

    async def list_guild_channels(self, guild_id: str) -> Any:
        return await self._request("GET", f"/api/v1/guilds/{guild_id}/channels")

    # --- guild config ---
    async def get_guild_config(self, guild_id: str) -> Any:
        return await self._request("GET", f"/api/v1/guilds/{guild_id}/config")

    async def update_guild_config(self, guild_id: str, **fields) -> Any:
        return await self._request("PUT", f"/api/v1/guilds/{guild_id}/config", json=fields)

    # --- email accounts ---
    async def list_email_accounts(self, user_id: str) -> Any:
        return await self._request("GET", "/api/v1/email-accounts", params={"user_id": user_id})

    # --- memory (internal, by explicit user_id) ---
    async def memory_count(self, user_id: str) -> Any:
        return await self._request("GET", "/api/v1/memory/count", params={"user_id": user_id})

    async def memory_search(self, user_id: str, query: str, limit: int = 10) -> Any:
        return await self._request(
            "GET", "/api/v1/memory/search", params={"user_id": user_id, "query": query, "limit": limit}
        )

    async def memory_delete_all(self, user_id: str) -> Any:
        return await self._request("DELETE", "/api/v1/memory", params={"user_id": user_id})

    # --- identity links ---
    async def resolve_link(self, prefixed_user_id: str) -> Any:
        return await self._request("GET", f"/api/v1/users/links/{prefixed_user_id}")

    async def resolve_link_optional(self, prefixed_user_id: str) -> Any | None:
        """Resolve a link, returning None if it does not exist (404)."""
        async with self._client() as client:
            resp = await client.get(f"/api/v1/users/links/{prefixed_user_id}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()

    async def list_user_links(self, canonical_id: str) -> Any:
        return await self._request("GET", f"/api/v1/users/{canonical_id}/links")

    async def create_link(self, **body) -> Any:
        return await self._request("POST", "/api/v1/users/links", json=body)

    async def delete_link(self, prefixed_user_id: str) -> Any:
        return await self._request("DELETE", f"/api/v1/users/links/{prefixed_user_id}")

    # --- MCP ---
    async def mcp_list_servers(self) -> Any:
        return await self._request("GET", "/api/v1/mcp/servers")

    async def mcp_server_status(self, name: str) -> Any:
        return await self._request("GET", f"/api/v1/mcp/servers/{name}/status")

    async def mcp_list_tools(self) -> Any:
        return await self._request("GET", "/api/v1/mcp/tools")

    async def mcp_lifecycle(self, name: str, action: str) -> Any:
        return await self._request("POST", f"/api/v1/mcp/servers/{name}/{action}")

    async def mcp_reload(self) -> Any:
        return await self._request("POST", "/api/v1/mcp/reload")

    async def mcp_search(self, query: str, page: int = 1, page_size: int = 10) -> Any:
        return await self._request(
            "GET",
            "/api/v1/mcp/search",
            params={"query": query, "page": page, "page_size": page_size},
        )

    async def mcp_install(self, source: str, name: str | None = None, installed_by: str | None = None) -> Any:
        return await self._request(
            "POST",
            "/api/v1/mcp/install",
            json={"source": source, "name": name, "installed_by": installed_by},
        )

    async def mcp_uninstall(self, name: str) -> Any:
        return await self._request("DELETE", f"/api/v1/mcp/servers/{name}")

    # --- MCP Smithery OAuth ---
    async def mcp_oauth_start(self, server: str) -> Any:
        return await self._request("POST", f"/api/v1/mcp/servers/{server}/oauth/start")

    async def mcp_oauth_complete(self, server: str, code: str) -> Any:
        return await self._request("POST", f"/api/v1/mcp/servers/{server}/oauth/complete", json={"code": code})

    async def mcp_oauth_status(self, server: str) -> Any:
        return await self._request("GET", f"/api/v1/mcp/servers/{server}/oauth/status")

    async def mcp_oauth_set_token(self, server: str, access_token: str, refresh_token: str | None = None) -> Any:
        return await self._request(
            "POST",
            f"/api/v1/mcp/servers/{server}/oauth/token",
            json={"access_token": access_token, "refresh_token": refresh_token},
        )
