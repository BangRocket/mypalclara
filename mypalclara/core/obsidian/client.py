"""Async HTTP client for the Obsidian Local REST API plugin.

The plugin exposes a vault over HTTP (or HTTPS with a self-signed cert).
All requests require an Authorization: Bearer <api-key> header.

Docs: https://github.com/coddingtonbear/obsidian-local-rest-api
"""

from __future__ import annotations

import json as _json
from typing import Any
from urllib.parse import quote

import httpx

from mypalclara.config.logging import get_logger
from mypalclara.core.obsidian.account import ObsidianAccountConfig

logger = get_logger("obsidian.client")

DEFAULT_TIMEOUT_SECONDS = 20.0


class ObsidianError(Exception):
    """Raised when the Obsidian REST API returns an error or is unreachable."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class ObsidianClient:
    """Thin async wrapper over the Local REST API endpoints Clara uses."""

    def __init__(self, config: ObsidianAccountConfig, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._config = config
        self._timeout = timeout

    @property
    def endpoint(self) -> str:
        return self._config.endpoint

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._config.api_token}",
            "Accept": "application/json",
        }
        if extra:
            headers.update(extra)
        return headers

    def _url(self, path: str) -> str:
        return f"{self.endpoint}{path}"

    async def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json: Any | None = None,
        content: str | bytes | None = None,
        params: dict[str, Any] | None = None,
    ) -> httpx.Response:
        url = self._url(path)
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                verify=self._config.verify_tls,
            ) as client:
                resp = await client.request(
                    method,
                    url,
                    headers=self._headers(headers),
                    json=json,
                    content=content,
                    params=params,
                )
        except httpx.RequestError as e:
            raise ObsidianError(f"Obsidian request failed: {e}") from e

        if resp.status_code >= 400:
            snippet = resp.text[:500] if resp.text else ""
            raise ObsidianError(
                f"Obsidian {method} {path} returned {resp.status_code}: {snippet}",
                status=resp.status_code,
            )
        return resp

    # -- Connectivity -----------------------------------------------------

    async def status(self) -> dict[str, Any]:
        """Hit the root status endpoint. Returns server info on success."""
        resp = await self._request("GET", "/")
        try:
            return resp.json()
        except _json.JSONDecodeError:
            return {"raw": resp.text}

    # -- Vault file operations -------------------------------------------

    async def list_directory(self, path: str = "") -> list[str]:
        """List files and subdirectories under a vault path.

        Args:
            path: Vault-relative path (e.g., "Journal" or ""). Trailing slash optional.

        Returns:
            List of names. Subdirectories are suffixed with "/".
        """
        normalized = path.strip("/")
        url_path = f"/vault/{_encode_path(normalized)}/" if normalized else "/vault/"
        resp = await self._request("GET", url_path)
        data = resp.json()
        files = data.get("files", data) if isinstance(data, dict) else data
        return list(files) if isinstance(files, list) else []

    async def read_note(self, path: str) -> str:
        """Fetch a note's full markdown content."""
        resp = await self._request(
            "GET",
            f"/vault/{_encode_path(path)}",
            headers={"Accept": "text/markdown"},
        )
        return resp.text

    async def create_note(self, path: str, content: str, overwrite: bool = False) -> None:
        """Create a note. PUT overwrites; POST appends when file exists."""
        method = "PUT" if overwrite else "POST"
        await self._request(
            method,
            f"/vault/{_encode_path(path)}",
            headers={"Content-Type": "text/markdown"},
            content=content,
        )

    async def update_note(
        self,
        path: str,
        content: str,
        *,
        operation: str = "append",
        target_type: str = "heading",
        target: str | None = None,
    ) -> None:
        """Patch a note via the PATCH endpoint.

        Args:
            path: Vault-relative path.
            content: Markdown to insert.
            operation: "append" | "prepend" | "replace".
            target_type: "heading" | "block" | "frontmatter".
            target: Target identifier (heading path, block id, or frontmatter key).
                    Required unless operation is "append" with no target (in which
                    case content is appended to end of file via POST fallback).
        """
        if operation not in ("append", "prepend", "replace"):
            raise ObsidianError(f"Invalid operation: {operation}")
        if target_type not in ("heading", "block", "frontmatter"):
            raise ObsidianError(f"Invalid target_type: {target_type}")

        if not target:
            # No explicit target — append to end of file.
            if operation != "append":
                raise ObsidianError(f"{operation} requires a target")
            await self._request(
                "POST",
                f"/vault/{_encode_path(path)}",
                headers={"Content-Type": "text/markdown"},
                content=content,
            )
            return

        await self._request(
            "PATCH",
            f"/vault/{_encode_path(path)}",
            headers={
                "Content-Type": "text/markdown",
                "Operation": operation,
                "Target-Type": target_type,
                "Target": target,
            },
            content=content,
        )

    async def delete_note(self, path: str) -> None:
        """Delete a note from the vault."""
        await self._request("DELETE", f"/vault/{_encode_path(path)}")

    # -- Search ------------------------------------------------------------

    async def search_simple(self, query: str, context_length: int = 100) -> list[dict[str, Any]]:
        """Full-text fuzzy search across the vault."""
        resp = await self._request(
            "POST",
            "/search/simple/",
            params={"query": query, "contextLength": context_length},
        )
        data = resp.json()
        return data if isinstance(data, list) else []

    # -- Tags --------------------------------------------------------------

    async def list_tags(self) -> list[dict[str, Any]]:
        """Return all tags in the vault with usage statistics."""
        resp = await self._request("GET", "/tags/")
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "tags" in data:
            return data["tags"]
        return []


def _encode_path(path: str) -> str:
    """URL-encode a vault path while preserving slashes."""
    return quote(path.strip("/"), safe="/")
