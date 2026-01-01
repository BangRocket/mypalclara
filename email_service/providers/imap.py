"""IMAP email provider for generic email servers."""

from __future__ import annotations

import asyncio
import email
import imaplib
import re
from datetime import datetime, timezone
from email.header import decode_header
from typing import TYPE_CHECKING

from config.logging import get_logger
from email_service.credentials import decrypt_credential
from email_service.providers.base import EmailMessage, EmailProvider

if TYPE_CHECKING:
    from db.models import EmailAccount

logger = get_logger("email.imap")

# Default IMAP settings
DEFAULT_IMAP_PORT = 993


class IMAPProvider(EmailProvider):
    """IMAP email provider for standard email servers."""

    def __init__(self, account: EmailAccount):
        """Initialize IMAP provider.

        Args:
            account: EmailAccount with IMAP credentials (encrypted password)
        """
        super().__init__(account)
        self._mail: imaplib.IMAP4_SSL | None = None

    async def connect(self) -> bool:
        """Connect to IMAP server."""
        try:
            server = self.account.imap_server
            port = self.account.imap_port or DEFAULT_IMAP_PORT
            username = self.account.imap_username or self.account.email_address
            password = decrypt_credential(self.account.imap_password or "")

            if not password:
                logger.error(f"No password configured for {self.account.email_address}")
                return False

            # Run blocking IMAP connection in thread pool
            loop = asyncio.get_event_loop()
            self._mail = await loop.run_in_executor(
                None, lambda: self._connect_sync(server, port, username, password)
            )
            self._connected = True
            logger.debug(f"Connected to IMAP server {server} as {username}")
            return True

        except Exception as e:
            logger.error(f"IMAP connection failed: {e}")
            self._connected = False
            return False

    def _connect_sync(
        self, server: str, port: int, username: str, password: str
    ) -> imaplib.IMAP4_SSL:
        """Synchronous IMAP connection (runs in thread pool)."""
        mail = imaplib.IMAP4_SSL(server, port)
        mail.login(username, password)
        return mail

    async def disconnect(self) -> None:
        """Disconnect from IMAP server."""
        if self._mail:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._mail.logout)
            except Exception as e:
                logger.debug(f"Error during IMAP disconnect: {e}")
            finally:
                self._mail = None
                self._connected = False

    async def test_connection(self) -> tuple[bool, str | None]:
        """Test IMAP connection with current credentials."""
        try:
            connected = await self.connect()
            if connected:
                await self.disconnect()
                return True, None
            return False, "Connection failed"
        except Exception as e:
            return False, str(e)

    async def get_new_messages(
        self,
        since_uid: str | None = None,
        since_timestamp: datetime | None = None,
        limit: int = 50,
    ) -> list[EmailMessage]:
        """Fetch new messages from IMAP server.

        Args:
            since_uid: Fetch messages with UID greater than this
            since_timestamp: Not used for IMAP (uses UID-based tracking)
            limit: Maximum messages to return

        Returns:
            List of new email messages
        """
        if not self._mail:
            if not await self.connect():
                return []

        try:
            loop = asyncio.get_event_loop()
            messages = await loop.run_in_executor(
                None, lambda: self._fetch_messages_sync(since_uid, limit)
            )
            return messages
        except Exception as e:
            logger.error(f"Error fetching IMAP messages: {e}")
            return []

    def _fetch_messages_sync(
        self, since_uid: str | None, limit: int
    ) -> list[EmailMessage]:
        """Synchronous message fetch (runs in thread pool)."""
        messages = []

        if not self._mail:
            return messages

        try:
            self._mail.select("INBOX")

            # Build search criteria
            if since_uid:
                # Fetch messages with UID > since_uid
                status, data = self._mail.uid("search", None, f"UID {int(since_uid) + 1}:*")
            else:
                # Fetch unseen messages
                status, data = self._mail.search(None, "UNSEEN")

            if status != "OK" or not data[0]:
                return messages

            msg_nums = data[0].split()[-limit:]  # Limit results

            for num in msg_nums:
                try:
                    msg = self._fetch_single_message(num, use_uid=bool(since_uid))
                    if msg:
                        messages.append(msg)
                except Exception as e:
                    logger.debug(f"Error fetching message {num}: {e}")
                    continue

        except Exception as e:
            logger.error(f"IMAP fetch error: {e}")

        return messages

    def _fetch_single_message(
        self, num: bytes, use_uid: bool = False
    ) -> EmailMessage | None:
        """Fetch a single message by number or UID."""
        if not self._mail:
            return None

        try:
            if use_uid:
                status, msg_data = self._mail.uid("fetch", num, "(UID RFC822)")
            else:
                status, msg_data = self._mail.fetch(num, "(UID RFC822)")

            if status != "OK" or not msg_data:
                return None

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    # Extract UID from response
                    uid = self._extract_uid(response_part[0])

                    # Parse email
                    msg = email.message_from_bytes(response_part[1])

                    from_addr = self._decode_header_value(msg.get("From", ""))
                    subject = self._decode_header_value(msg.get("Subject", "(No Subject)"))
                    date_str = msg.get("Date", "")
                    received_at = self._parse_date(date_str)
                    snippet = self._get_snippet(msg)
                    has_attachments = self._has_attachments(msg)

                    return EmailMessage(
                        uid=uid or num.decode(),
                        from_addr=from_addr,
                        subject=subject,
                        snippet=snippet,
                        received_at=received_at,
                        has_attachments=has_attachments,
                    )

        except Exception as e:
            logger.debug(f"Error parsing message: {e}")

        return None

    def _extract_uid(self, response_bytes: bytes) -> str | None:
        """Extract UID from IMAP response."""
        try:
            response = response_bytes.decode()
            match = re.search(r"UID (\d+)", response)
            if match:
                return match.group(1)
        except Exception:
            pass
        return None

    def _decode_header_value(self, value: str) -> str:
        """Decode email header (handles encoded words)."""
        if not value:
            return ""
        try:
            decoded_parts = decode_header(value)
            result = []
            for part, charset in decoded_parts:
                if isinstance(part, bytes):
                    result.append(part.decode(charset or "utf-8", errors="replace"))
                else:
                    result.append(part)
            return "".join(result)
        except Exception:
            return value

    def _parse_date(self, date_str: str) -> datetime:
        """Parse email date string to datetime."""
        if not date_str:
            return datetime.now(timezone.utc).replace(tzinfo=None)

        try:
            # Try common formats
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str).replace(tzinfo=None)
        except Exception:
            return datetime.now(timezone.utc).replace(tzinfo=None)

    def _get_snippet(self, msg: email.message.Message, max_len: int = 200) -> str:
        """Extract text snippet from email body."""
        try:
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            text = payload.decode("utf-8", errors="replace")
                            return self._clean_snippet(text, max_len)
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    text = payload.decode("utf-8", errors="replace")
                    return self._clean_snippet(text, max_len)
        except Exception:
            pass
        return ""

    def _clean_snippet(self, text: str, max_len: int) -> str:
        """Clean and truncate snippet text."""
        # Remove excessive whitespace
        text = " ".join(text.split())
        if len(text) > max_len:
            return text[:max_len] + "..."
        return text

    def _has_attachments(self, msg: email.message.Message) -> bool:
        """Check if email has attachments."""
        if not msg.is_multipart():
            return False

        for part in msg.walk():
            content_disposition = part.get("Content-Disposition", "")
            if "attachment" in content_disposition.lower():
                return True
        return False
