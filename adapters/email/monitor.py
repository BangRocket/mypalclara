"""Email monitoring module for Clara Gateway.

Provides EmailMonitor class with both sync and async methods for IMAP operations.
Extracted from email_monitor.py for gateway integration.
"""

from __future__ import annotations

import asyncio
import email
import imaplib
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from email.header import decode_header

# Email configuration - loaded from environment
EMAIL_ADDRESS = os.environ.get("CLARA_EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("CLARA_EMAIL_PASSWORD")
IMAP_SERVER = os.getenv("CLARA_IMAP_SERVER", "imap.titan.email")
IMAP_PORT = int(os.getenv("CLARA_IMAP_PORT", "993"))

# Thread pool for blocking IMAP operations
BLOCKING_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="email-io-")


@dataclass
class EmailInfo:
    """Represents an email message."""

    uid: str
    from_addr: str
    subject: str
    date: str
    preview: str = ""
    body: str = ""
    is_read: bool = True


class EmailMonitor:
    """Monitors an IMAP inbox for new messages.

    Provides both synchronous and asynchronous methods for email operations.
    Async methods use ThreadPoolExecutor to avoid blocking the event loop.
    """

    def __init__(self) -> None:
        self.seen_uids: set[str] = set()
        self.initialized = False
        self.last_check: datetime | None = None
        self.last_error: str | None = None

    def _connect(self) -> imaplib.IMAP4_SSL:
        """Create IMAP connection."""
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        return mail

    def _decode_header_value(self, value: str) -> str:
        """Decode email header (handles encoded words)."""
        if not value:
            return ""
        decoded_parts = decode_header(value)
        result = []
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                result.append(part)
        return "".join(result)

    def _get_email_preview(self, msg) -> str:
        """Extract a text preview from email body."""
        preview = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            preview = payload.decode("utf-8", errors="replace")[:200]
                            break
                    except Exception:
                        pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    preview = payload.decode("utf-8", errors="replace")[:200]
            except Exception:
                pass
        return (
            preview.strip().replace("\n", " ")[:150] + "..."
            if len(preview) > 150
            else preview.strip()
        )

    def _get_email_body(self, msg) -> str:
        """Extract the full text body from an email."""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode("utf-8", errors="replace")
                            break
                    except Exception:
                        pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="replace")
            except Exception:
                pass
        return body.strip()

    def check_emails(self, unseen_only: bool = True) -> tuple[list[EmailInfo], str | None]:
        """Check inbox for emails.

        Args:
            unseen_only: If True, only return unseen messages

        Returns:
            tuple: (list of EmailInfo, error message or None)
        """
        try:
            mail = self._connect()
            mail.select("INBOX")

            # Search for messages
            search_criteria = "UNSEEN" if unseen_only else "ALL"
            status, data = mail.search(None, search_criteria)

            if status != "OK":
                mail.logout()
                return [], f"Search failed: {status}"

            emails = []
            message_nums = data[0].split()

            for num in message_nums[-10:]:  # Limit to last 10
                status, msg_data = mail.fetch(num, "(UID RFC822.HEADER)")
                if status != "OK":
                    continue

                # Get UID
                uid_match = None
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        uid_part = response_part[0].decode()
                        if "UID" in uid_part:
                            match = re.search(r"UID (\d+)", uid_part)
                            if match:
                                uid_match = match.group(1)

                        # Parse headers
                        msg = email.message_from_bytes(response_part[1])
                        from_addr = self._decode_header_value(msg.get("From", ""))
                        subject = self._decode_header_value(
                            msg.get("Subject", "(No Subject)")
                        )
                        date = msg.get("Date", "")

                        emails.append(
                            EmailInfo(
                                uid=uid_match or str(num.decode()),
                                from_addr=from_addr,
                                subject=subject,
                                date=date,
                            )
                        )

            mail.logout()
            self.last_check = datetime.now(UTC)
            self.last_error = None
            return emails, None

        except Exception as e:
            self.last_error = str(e)
            return [], str(e)

    def get_new_emails(self) -> tuple[list[EmailInfo], str | None]:
        """Check for new emails since last check.

        Returns emails that haven't been seen before.
        """
        emails, error = self.check_emails(unseen_only=True)

        if error:
            return [], error

        if not self.initialized:
            # First run - just record what's there, don't notify
            self.seen_uids = {e.uid for e in emails}
            self.initialized = True
            return [], None

        # Find new emails
        new_emails = [e for e in emails if e.uid not in self.seen_uids]

        # Update seen set
        self.seen_uids.update(e.uid for e in emails)

        return new_emails, None

    def get_all_emails(self, limit: int = 10) -> tuple[list[EmailInfo], str | None]:
        """Get all recent emails (for on-demand check)."""
        try:
            mail = self._connect()
            mail.select("INBOX")

            status, data = mail.search(None, "ALL")
            if status != "OK":
                mail.logout()
                return [], f"Search failed: {status}"

            emails = []
            message_nums = data[0].split()

            # Get last N messages
            for num in message_nums[-limit:]:
                status, msg_data = mail.fetch(num, "(UID FLAGS RFC822.HEADER)")
                if status != "OK":
                    continue

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        # Check flags for seen status
                        flags_part = response_part[0].decode()
                        is_seen = "\\Seen" in flags_part

                        # Get UID
                        uid_match = re.search(r"UID (\d+)", flags_part)
                        uid = uid_match.group(1) if uid_match else str(num.decode())

                        # Parse headers
                        msg = email.message_from_bytes(response_part[1])
                        from_addr = self._decode_header_value(msg.get("From", ""))
                        subject = self._decode_header_value(
                            msg.get("Subject", "(No Subject)")
                        )
                        date = msg.get("Date", "")

                        emails.append(
                            EmailInfo(
                                uid=uid,
                                from_addr=from_addr,
                                subject=subject,
                                date=date,
                                is_read=is_seen,
                            )
                        )

            mail.logout()
            self.last_check = datetime.now(UTC)
            return emails, None

        except Exception as e:
            return [], str(e)

    def search_emails(
        self,
        query: str | None = None,
        from_addr: str | None = None,
        subject: str | None = None,
        since_days: int | None = None,
        limit: int = 20,
    ) -> tuple[list[EmailInfo], str | None]:
        """Search emails with various criteria.

        Args:
            query: Search in subject and body
            from_addr: Filter by sender
            subject: Filter by subject line
            since_days: Only emails from the last N days
            limit: Max results to return

        Returns:
            List of matching emails and optional error
        """
        try:
            mail = self._connect()
            mail.select("INBOX")

            # Build IMAP search criteria
            criteria = []

            if from_addr:
                criteria.append(f'FROM "{from_addr}"')

            if subject:
                criteria.append(f'SUBJECT "{subject}"')

            if since_days:
                from datetime import timedelta

                since_date = (datetime.now(UTC) - timedelta(days=since_days)).strftime(
                    "%d-%b-%Y"
                )
                criteria.append(f'SINCE "{since_date}"')

            if query:
                # Search in subject OR body - IMAP requires separate searches
                criteria.append(f'OR SUBJECT "{query}" BODY "{query}"')

            # If no criteria, get recent emails
            search_string = " ".join(criteria) if criteria else "ALL"

            status, data = mail.search(None, search_string)
            if status != "OK":
                mail.logout()
                return [], f"Search failed: {status}"

            emails = []
            message_nums = data[0].split()

            # Get last N matches (most recent)
            for num in message_nums[-limit:]:
                status, msg_data = mail.fetch(num, "(UID FLAGS RFC822.HEADER)")
                if status != "OK":
                    continue

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        flags_part = response_part[0].decode()
                        is_seen = "\\Seen" in flags_part

                        uid_match = re.search(r"UID (\d+)", flags_part)
                        uid = uid_match.group(1) if uid_match else str(num.decode())

                        msg = email.message_from_bytes(response_part[1])
                        from_addr_parsed = self._decode_header_value(msg.get("From", ""))
                        subject_parsed = self._decode_header_value(
                            msg.get("Subject", "(No Subject)")
                        )
                        date = msg.get("Date", "")

                        emails.append(
                            EmailInfo(
                                uid=uid,
                                from_addr=from_addr_parsed,
                                subject=subject_parsed,
                                date=date,
                                is_read=is_seen,
                            )
                        )

            mail.logout()
            return emails, None

        except Exception as e:
            return [], str(e)

    def get_full_email(self, uid: str) -> tuple[EmailInfo | None, str | None]:
        """Fetch a complete email including body by UID."""
        try:
            mail = self._connect()
            mail.select("INBOX")

            # Fetch full message by UID
            status, msg_data = mail.uid("fetch", uid, "(RFC822)")
            if status != "OK":
                mail.logout()
                return None, f"Failed to fetch email {uid}"

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    from_addr = self._decode_header_value(msg.get("From", ""))
                    subject = self._decode_header_value(
                        msg.get("Subject", "(No Subject)")
                    )
                    date = msg.get("Date", "")
                    body = self._get_email_body(msg)

                    mail.logout()
                    return (
                        EmailInfo(
                            uid=uid,
                            from_addr=from_addr,
                            subject=subject,
                            date=date,
                            body=body,
                            is_read=True,
                        ),
                        None,
                    )

            mail.logout()
            return None, "Email not found"

        except Exception as e:
            return None, str(e)

    # Async wrapper methods using ThreadPoolExecutor

    async def check_emails_async(
        self, unseen_only: bool = True
    ) -> tuple[list[EmailInfo], str | None]:
        """Async version - runs sync method in executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            BLOCKING_EXECUTOR, lambda: self.check_emails(unseen_only)
        )

    async def get_new_emails_async(self) -> tuple[list[EmailInfo], str | None]:
        """Async version - runs sync method in executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(BLOCKING_EXECUTOR, self.get_new_emails)

    async def get_all_emails_async(
        self, limit: int = 10
    ) -> tuple[list[EmailInfo], str | None]:
        """Async version - runs sync method in executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            BLOCKING_EXECUTOR, lambda: self.get_all_emails(limit)
        )

    async def search_emails_async(
        self,
        query: str | None = None,
        from_addr: str | None = None,
        subject: str | None = None,
        since_days: int | None = None,
        limit: int = 20,
    ) -> tuple[list[EmailInfo], str | None]:
        """Async version - runs sync method in executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            BLOCKING_EXECUTOR,
            lambda: self.search_emails(query, from_addr, subject, since_days, limit),
        )

    async def get_full_email_async(
        self, uid: str
    ) -> tuple[EmailInfo | None, str | None]:
        """Async version - runs sync method in executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            BLOCKING_EXECUTOR, lambda: self.get_full_email(uid)
        )
