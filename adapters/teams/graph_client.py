"""Microsoft Graph API client for Teams adapter.

Provides conversation history and file upload capabilities using
the Microsoft Graph REST API.
"""

from __future__ import annotations

import asyncio
import base64
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import aiohttp

from config.logging import get_logger

logger = get_logger("adapters.teams.graph")

# Graph API endpoints
GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
GRAPH_BETA_URL = "https://graph.microsoft.com/beta"
TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"

# Graph API requires a real tenant ID, not botframework.com
# Set TEAMS_GRAPH_TENANT_ID to enable Graph API features (conversation history, file uploads)
DEFAULT_TENANT = None


class GraphClient:
    """Microsoft Graph API client for Teams operations.

    Handles authentication and provides methods for:
    - Fetching conversation/chat history
    - Uploading files to OneDrive
    - Creating shareable links
    """

    def __init__(
        self,
        app_id: str | None = None,
        app_password: str | None = None,
        tenant_id: str | None = None,
    ) -> None:
        """Initialize the Graph client.

        Args:
            app_id: Azure Bot App ID (defaults to TEAMS_APP_ID env var)
            app_password: Azure Bot App Password (defaults to TEAMS_APP_PASSWORD env var)
            tenant_id: Azure tenant ID (defaults to TEAMS_TENANT_ID or botframework.com)
        """
        self.app_id = app_id or os.getenv("TEAMS_APP_ID", "")
        self.app_password = app_password or os.getenv("TEAMS_APP_PASSWORD", "")
        self.tenant_id = tenant_id or os.getenv("TEAMS_GRAPH_TENANT_ID", DEFAULT_TENANT)

        # Graph API is disabled if no tenant is configured
        self._enabled = bool(self.tenant_id)
        if not self._enabled:
            logger.info(
                "Graph API disabled - set TEAMS_GRAPH_TENANT_ID to enable " "conversation history and file uploads"
            )

        self._access_token: str | None = None
        self._token_expiry: datetime | None = None
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _get_token(self) -> str:
        """Get a valid access token, refreshing if needed.

        Returns:
            Access token string
        """
        async with self._lock:
            # Check if current token is still valid (with 5 min buffer)
            if self._access_token and self._token_expiry and datetime.now() < self._token_expiry - timedelta(minutes=5):
                return self._access_token

            # Request new token
            session = await self._ensure_session()
            token_url = TOKEN_URL.format(tenant=self.tenant_id)

            data = {
                "client_id": self.app_id,
                "client_secret": self.app_password,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            }

            try:
                async with session.post(token_url, data=data) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"Token request failed: {resp.status} - {error_text}")
                        raise RuntimeError(f"Failed to get Graph token: {resp.status}")

                    result = await resp.json()
                    self._access_token = result["access_token"]
                    expires_in = result.get("expires_in", 3600)
                    self._token_expiry = datetime.now() + timedelta(seconds=expires_in)

                    logger.debug(f"Obtained Graph token, expires in {expires_in}s")
                    return self._access_token

            except aiohttp.ClientError as e:
                logger.error(f"Token request error: {e}")
                raise

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        json: dict | None = None,
        data: bytes | None = None,
        headers: dict | None = None,
        use_beta: bool = False,
    ) -> dict[str, Any]:
        """Make an authenticated Graph API request.

        Args:
            method: HTTP method
            endpoint: API endpoint (without base URL)
            json: JSON body
            data: Raw bytes body
            headers: Additional headers
            use_beta: Use beta API endpoint

        Returns:
            Response JSON
        """
        token = await self._get_token()
        session = await self._ensure_session()

        base_url = GRAPH_BETA_URL if use_beta else GRAPH_BASE_URL
        url = f"{base_url}{endpoint}"

        req_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        if headers:
            req_headers.update(headers)

        try:
            async with session.request(
                method,
                url,
                json=json,
                data=data,
                headers=req_headers,
            ) as resp:
                if resp.status >= 400:
                    error_text = await resp.text()
                    logger.error(f"Graph API error: {resp.status} - {error_text}")
                    return {"error": {"code": resp.status, "message": error_text}}

                if resp.status == 204:  # No content
                    return {}

                return await resp.json()

        except aiohttp.ClientError as e:
            logger.error(f"Graph API request error: {e}")
            return {"error": {"code": "NetworkError", "message": str(e)}}

    async def get_chat_messages(
        self,
        chat_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch recent messages from a Teams chat.

        Permissions (choose one):
        - RSC: ChatMessage.Read.Chat (scoped to installed chats, recommended)
        - Application: Chat.Read.WhereInstalled (scoped to installed chats)
        - Application: Chat.Read.All (tenant-wide, not recommended)

        Note: RSC permissions don't support reading 1:1 personal chat messages.
        For personal chats with RSC, this will return an empty list.

        Args:
            chat_id: The Teams chat/conversation ID
            limit: Maximum messages to fetch

        Returns:
            List of message dicts with role, content, author
        """
        if not self._enabled:
            return []

        endpoint = f"/chats/{chat_id}/messages?$top={limit}&$orderby=createdDateTime desc"

        result = await self._request("GET", endpoint)

        if "error" in result:
            logger.warning(f"Failed to get chat messages: {result['error']}")
            return []

        messages = []
        for msg in reversed(result.get("value", [])):
            # Skip system messages
            if msg.get("messageType") != "message":
                continue

            body = msg.get("body", {})
            content = body.get("content", "")

            # Strip HTML if present
            if body.get("contentType") == "html":
                content = self._strip_html(content)

            from_user = msg.get("from", {}).get("user", {})
            author = from_user.get("displayName", "Unknown")

            # Determine role based on whether it's from the bot
            # Bot messages have from.application instead of from.user
            is_bot = msg.get("from", {}).get("application") is not None

            messages.append(
                {
                    "role": "assistant" if is_bot else "user",
                    "content": content,
                    "author": author,
                    "timestamp": msg.get("createdDateTime"),
                }
            )

        return messages

    async def get_channel_messages(
        self,
        team_id: str,
        channel_id: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch recent messages from a Teams channel.

        Permissions (choose one):
        - RSC: ChannelMessage.Read.Group (scoped to installed teams, recommended)
        - Application: ChannelMessage.Read.All (tenant-wide, not recommended)

        Args:
            team_id: The Teams team ID
            channel_id: The channel ID
            limit: Maximum messages to fetch

        Returns:
            List of message dicts
        """
        if not self._enabled:
            return []

        endpoint = f"/teams/{team_id}/channels/{channel_id}/messages?$top={limit}"

        result = await self._request("GET", endpoint)

        if "error" in result:
            logger.warning(f"Failed to get channel messages: {result['error']}")
            return []

        messages = []
        for msg in reversed(result.get("value", [])):
            if msg.get("messageType") != "message":
                continue

            body = msg.get("body", {})
            content = body.get("content", "")

            if body.get("contentType") == "html":
                content = self._strip_html(content)

            from_user = msg.get("from", {}).get("user", {})
            author = from_user.get("displayName", "Unknown")
            is_bot = msg.get("from", {}).get("application") is not None

            messages.append(
                {
                    "role": "assistant" if is_bot else "user",
                    "content": content,
                    "author": author,
                    "timestamp": msg.get("createdDateTime"),
                }
            )

        return messages

    async def upload_file_to_onedrive(
        self,
        file_path: str | Path,
        folder: str = "Clara Files",
    ) -> dict[str, Any] | None:
        """Upload a file to the bot's OneDrive.

        Note: Requires Files.ReadWrite.All application permission.
        There is no RSC equivalent for file permissions.

        Args:
            file_path: Local file path
            folder: OneDrive folder name

        Returns:
            Dict with id, name, webUrl, or None on failure
        """
        if not self._enabled:
            return None

        path = Path(file_path)
        if not path.exists():
            logger.error(f"File not found: {file_path}")
            return None

        filename = path.name
        file_size = path.stat().st_size

        # For small files (<4MB), use simple upload
        if file_size < 4 * 1024 * 1024:
            return await self._simple_upload(path, folder, filename)
        else:
            # For larger files, use upload session
            return await self._resumable_upload(path, folder, filename)

    async def _simple_upload(
        self,
        path: Path,
        folder: str,
        filename: str,
    ) -> dict[str, Any] | None:
        """Simple upload for files <4MB."""
        content = path.read_bytes()

        # Upload to app's drive (bot's OneDrive)
        endpoint = f"/drive/root:/{folder}/{filename}:/content"

        result = await self._request(
            "PUT",
            endpoint,
            data=content,
            headers={"Content-Type": "application/octet-stream"},
        )

        if "error" in result:
            logger.error(f"Upload failed: {result['error']}")
            return None

        return {
            "id": result.get("id"),
            "name": result.get("name"),
            "webUrl": result.get("webUrl"),
            "size": result.get("size"),
        }

    async def _resumable_upload(
        self,
        path: Path,
        folder: str,
        filename: str,
    ) -> dict[str, Any] | None:
        """Resumable upload for larger files."""
        # Create upload session
        endpoint = f"/drive/root:/{folder}/{filename}:/createUploadSession"

        session_result = await self._request(
            "POST",
            endpoint,
            json={
                "item": {
                    "@microsoft.graph.conflictBehavior": "rename",
                    "name": filename,
                }
            },
        )

        if "error" in session_result:
            logger.error(f"Failed to create upload session: {session_result['error']}")
            return None

        upload_url = session_result.get("uploadUrl")
        if not upload_url:
            logger.error("No upload URL in session response")
            return None

        # Upload in chunks
        file_size = path.stat().st_size
        chunk_size = 320 * 1024 * 10  # 3.2MB chunks

        session = await self._ensure_session()

        with open(path, "rb") as f:
            offset = 0
            while offset < file_size:
                chunk = f.read(chunk_size)
                chunk_len = len(chunk)
                end = offset + chunk_len - 1

                headers = {
                    "Content-Length": str(chunk_len),
                    "Content-Range": f"bytes {offset}-{end}/{file_size}",
                }

                async with session.put(upload_url, data=chunk, headers=headers) as resp:
                    if resp.status not in (200, 201, 202):
                        error_text = await resp.text()
                        logger.error(f"Chunk upload failed: {resp.status} - {error_text}")
                        return None

                    if resp.status in (200, 201):
                        # Upload complete
                        result = await resp.json()
                        return {
                            "id": result.get("id"),
                            "name": result.get("name"),
                            "webUrl": result.get("webUrl"),
                            "size": result.get("size"),
                        }

                offset += chunk_len

        logger.error("Upload completed without final response")
        return None

    async def create_sharing_link(
        self,
        item_id: str,
        link_type: str = "view",
    ) -> str | None:
        """Create a sharing link for a OneDrive file.

        Args:
            item_id: OneDrive item ID
            link_type: "view" or "edit"

        Returns:
            Sharing URL or None
        """
        if not self._enabled:
            return None

        endpoint = f"/drive/items/{item_id}/createLink"

        result = await self._request(
            "POST",
            endpoint,
            json={
                "type": link_type,
                "scope": "organization",  # or "anonymous" for external
            },
        )

        if "error" in result:
            logger.error(f"Failed to create sharing link: {result['error']}")
            return None

        return result.get("link", {}).get("webUrl")

    def _strip_html(self, html: str) -> str:
        """Strip HTML tags from content.

        Args:
            html: HTML string

        Returns:
            Plain text
        """
        import re

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", html)
        # Decode common entities
        text = text.replace("&nbsp;", " ")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&amp;", "&")
        text = text.replace("&quot;", '"')
        return text.strip()


# Module-level instance for shared use
_graph_client: GraphClient | None = None


def get_graph_client() -> GraphClient:
    """Get or create the shared Graph client instance."""
    global _graph_client
    if _graph_client is None:
        _graph_client = GraphClient()
    return _graph_client
