"""Gmail API provider using existing Google OAuth tokens."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx

from config.logging import get_logger
from email_service.providers.base import EmailMessage, EmailProvider

if TYPE_CHECKING:
    from db.models import EmailAccount

logger = get_logger("email.gmail")

# Gmail API base URL
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"


class GmailProvider(EmailProvider):
    """Gmail provider using Google OAuth and Gmail API."""

    def __init__(self, account: EmailAccount):
        """Initialize Gmail provider.

        Args:
            account: EmailAccount with provider_type="gmail"
                    (uses GoogleOAuthToken via user_id)
        """
        super().__init__(account)
        self._access_token: str | None = None

    async def connect(self) -> bool:
        """Get valid access token from Google OAuth."""
        try:
            # Import here to avoid circular imports
            from tools.google_oauth import get_valid_token

            token = await get_valid_token(self.account.user_id)
            if token:
                self._access_token = token
                self._connected = True
                logger.debug(f"Gmail connected for user {self.account.user_id}")
                return True

            logger.warning(f"No valid Gmail token for user {self.account.user_id}")
            self._connected = False
            return False

        except Exception as e:
            logger.error(f"Gmail connection failed: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Clear access token (no persistent connection to close)."""
        self._access_token = None
        self._connected = False

    async def test_connection(self) -> tuple[bool, str | None]:
        """Test Gmail connection by fetching profile."""
        try:
            if not await self.connect():
                return False, "No valid Google OAuth token. Please reconnect Google."

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GMAIL_API_BASE}/users/me/profile",
                    headers={"Authorization": f"Bearer {self._access_token}"},
                    timeout=30.0,
                )

            if response.status_code == 200:
                return True, None
            elif response.status_code == 403:
                return False, "Gmail access not authorized. Please reconnect Google with email permissions."
            else:
                return False, f"Gmail API error: {response.status_code}"

        except Exception as e:
            return False, str(e)

    async def get_new_messages(
        self,
        since_uid: str | None = None,
        since_timestamp: datetime | None = None,
        limit: int = 50,
    ) -> list[EmailMessage]:
        """Fetch new messages from Gmail.

        Args:
            since_uid: Gmail message ID to fetch after (not used - uses historyId)
            since_timestamp: Fetch messages after this time
            limit: Maximum messages to return

        Returns:
            List of new email messages
        """
        if not self._connected:
            if not await self.connect():
                return []

        try:
            # Build query
            query_parts = ["in:inbox"]
            if since_timestamp:
                # Gmail uses Unix timestamp in seconds
                timestamp = int(since_timestamp.timestamp())
                query_parts.append(f"after:{timestamp}")

            query = " ".join(query_parts)

            # List messages
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GMAIL_API_BASE}/users/me/messages",
                    headers={"Authorization": f"Bearer {self._access_token}"},
                    params={
                        "q": query,
                        "maxResults": limit,
                    },
                    timeout=30.0,
                )

            if response.status_code != 200:
                logger.error(f"Gmail list messages failed: {response.status_code}")
                return []

            data = response.json()
            messages = data.get("messages", [])

            # Filter by since_uid if provided
            if since_uid:
                # Only return messages newer than since_uid
                new_messages = []
                for msg in messages:
                    if msg["id"] == since_uid:
                        break
                    new_messages.append(msg)
                messages = new_messages

            # Fetch full message details
            result = []
            for msg_ref in messages:
                try:
                    email_msg = await self._fetch_message(msg_ref["id"])
                    if email_msg:
                        result.append(email_msg)
                except Exception as e:
                    logger.debug(f"Error fetching message {msg_ref['id']}: {e}")

            return result

        except Exception as e:
            logger.error(f"Gmail get_new_messages failed: {e}")
            return []

    async def _fetch_message(self, message_id: str) -> EmailMessage | None:
        """Fetch full message details by ID."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GMAIL_API_BASE}/users/me/messages/{message_id}",
                    headers={"Authorization": f"Bearer {self._access_token}"},
                    params={"format": "full"},
                    timeout=30.0,
                )

            if response.status_code != 200:
                return None

            data = response.json()
            return self._parse_message(data)

        except Exception as e:
            logger.debug(f"Error fetching Gmail message {message_id}: {e}")
            return None

    def _parse_message(self, data: dict) -> EmailMessage:
        """Parse Gmail API message response."""
        headers = {h["name"].lower(): h["value"] for h in data.get("payload", {}).get("headers", [])}

        from_addr = headers.get("from", "")
        subject = headers.get("subject", "(No Subject)")
        date_str = headers.get("date", "")

        # Parse date
        received_at = self._parse_date(date_str)

        # Get snippet (Gmail provides this)
        snippet = data.get("snippet", "")

        # Check for attachments
        has_attachments = self._has_attachments(data.get("payload", {}))

        return EmailMessage(
            uid=data["id"],
            from_addr=from_addr,
            subject=subject,
            snippet=snippet[:200] if snippet else "",
            received_at=received_at,
            has_attachments=has_attachments,
        )

    def _parse_date(self, date_str: str) -> datetime:
        """Parse email date string."""
        if not date_str:
            return datetime.now(timezone.utc).replace(tzinfo=None)

        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str).replace(tzinfo=None)
        except Exception:
            return datetime.now(timezone.utc).replace(tzinfo=None)

    def _has_attachments(self, payload: dict) -> bool:
        """Check if message has attachments."""
        # Check for attachment parts
        parts = payload.get("parts", [])
        for part in parts:
            if part.get("filename"):
                return True
            # Recursively check nested parts
            if self._has_attachments(part):
                return True
        return False

    async def get_unread_count(self) -> int:
        """Get count of unread messages in inbox."""
        if not self._connected:
            if not await self.connect():
                return 0

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GMAIL_API_BASE}/users/me/labels/INBOX",
                    headers={"Authorization": f"Bearer {self._access_token}"},
                    timeout=30.0,
                )

            if response.status_code == 200:
                data = response.json()
                return data.get("messagesUnread", 0)

        except Exception as e:
            logger.debug(f"Error getting unread count: {e}")

        return 0
