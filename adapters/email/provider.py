"""Email provider for Clara Gateway.

Polls email accounts and emits events for new messages through the gateway event system.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Any

from config.logging import get_logger
from gateway.events import Event, EventType, emit
from gateway.providers.base import PlatformMessage, Provider

from adapters.email.monitor import EmailInfo, EmailMonitor

logger = get_logger("adapters.email.provider")

# Configuration
CHECK_INTERVAL = int(os.getenv("CLARA_EMAIL_CHECK_INTERVAL", "60"))
NOTIFY_USER_ID = os.getenv("CLARA_EMAIL_NOTIFY_USER", "").strip()


class EmailProvider(Provider):
    """Provider that monitors email accounts and emits alert events.

    Uses the gateway event system to notify other providers (e.g., Discord)
    about new emails, rather than directly coupling to Discord.

    Note: EmailProvider is asymmetric - it receives emails and emits events,
    but doesn't send responses back to email. The send_response() method
    raises NotImplementedError as email is a receive-only provider.

    Attributes:
        monitor: The underlying EmailMonitor instance
        check_interval: Seconds between email checks
    """

    def __init__(
        self,
        check_interval: int = CHECK_INTERVAL,
        notify_user_id: str | None = None,
    ) -> None:
        """Initialize the email provider.

        Args:
            check_interval: Seconds between email checks
            notify_user_id: User ID to target for alerts (platform-prefixed)
        """
        super().__init__()
        self.monitor = EmailMonitor()
        self.check_interval = check_interval
        self.notify_user_id = notify_user_id or (
            f"discord-{NOTIFY_USER_ID}" if NOTIFY_USER_ID else None
        )

        self._poll_task: asyncio.Task[None] | None = None
        self._started_at: datetime | None = None
        self._emails_processed = 0
        self._last_check: datetime | None = None
        self._last_error: str | None = None

    @property
    def name(self) -> str:
        """Return provider identifier.

        Returns:
            The string "email"
        """
        return "email"

    async def start(self) -> None:
        """Start the email polling loop."""
        if self._running:
            logger.warning("EmailProvider already running")
            return

        # Check if email is configured
        email_addr = os.getenv("CLARA_EMAIL_ADDRESS")
        email_pass = os.getenv("CLARA_EMAIL_PASSWORD")

        if not email_addr or not email_pass:
            logger.warning(
                "Email monitoring disabled - CLARA_EMAIL_ADDRESS or CLARA_EMAIL_PASSWORD not set"
            )
            return

        self._running = True
        self._started_at = datetime.now()
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info(
            f"EmailProvider started - polling {email_addr} every {self.check_interval}s"
        )

    async def stop(self) -> None:
        """Stop the email polling loop."""
        self._running = False

        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None

        logger.info("EmailProvider stopped")

    async def _poll_loop(self) -> None:
        """Main polling loop - checks for new emails periodically."""
        while self._running:
            try:
                await self._check_and_emit()
            except Exception as e:
                self._last_error = str(e)
                logger.exception(f"Email poll error: {e}")

            await asyncio.sleep(self.check_interval)

    async def _check_and_emit(self) -> None:
        """Check for new emails and emit events for each."""
        new_emails, error = await self.monitor.get_new_emails_async()
        self._last_check = datetime.now()

        if error:
            self._last_error = error
            logger.warning(f"Email check error: {error}")
            return

        if not new_emails:
            return

        logger.info(f"Found {len(new_emails)} new email(s)")

        for email_info in new_emails:
            await self._emit_email_alert(email_info)
            self._emails_processed += 1

    async def _emit_email_alert(self, email_info: EmailInfo) -> None:
        """Emit an event for a new email.

        Args:
            email_info: The email to alert about
        """
        # Determine alert channel - use DM to notify_user_id
        channel_id = f"dm-{self.notify_user_id}" if self.notify_user_id else None

        await emit(
            Event(
                type=EventType.MESSAGE_RECEIVED,
                platform="email",
                user_id=self.notify_user_id,
                channel_id=channel_id,
                data={
                    "provider": "email",
                    "uid": email_info.uid,
                    "from": email_info.from_addr,
                    "subject": email_info.subject,
                    "date": email_info.date,
                    "preview": email_info.preview,
                    "is_read": email_info.is_read,
                },
            )
        )
        logger.debug(f"Emitted email alert for: {email_info.subject}")

    def get_stats(self) -> dict[str, Any]:
        """Get provider statistics."""
        uptime = None
        if self._started_at:
            uptime = int((datetime.now() - self._started_at).total_seconds())

        return {
            "running": self._running,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "uptime_seconds": uptime,
            "emails_processed": self._emails_processed,
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "last_error": self._last_error,
            "check_interval": self.check_interval,
        }

    def normalize_message(self, platform_message: Any) -> PlatformMessage:
        """Convert a platform-specific message to normalized format.

        EmailProvider doesn't normalize incoming messages - it emits events
        directly when new emails are detected. This method is required by
        Provider ABC but not used by EmailProvider's architecture.

        Args:
            platform_message: Unused (EmailProvider emits events directly)

        Raises:
            NotImplementedError: EmailProvider emits events directly,
                doesn't normalize incoming messages
        """
        raise NotImplementedError(
            "EmailProvider emits events directly and doesn't normalize incoming messages. "
            "Email alerts are sent via the gateway event system (EventType.MESSAGE_RECEIVED)."
        )

    async def send_response(
        self,
        context: dict[str, Any],
        content: str,
        files: list[str] | None = None,
    ) -> None:
        """Send a response back through the platform.

        EmailProvider is receive-only and doesn't send responses back to email.
        Responses are sent through other providers (like Discord) via the event system.

        Args:
            context: Unused (EmailProvider doesn't send responses)
            content: Unused (EmailProvider doesn't send responses)
            files: Unused (EmailProvider doesn't send responses)

        Raises:
            NotImplementedError: EmailProvider is receive-only and doesn't
                send responses back to email accounts
        """
        raise NotImplementedError(
            "EmailProvider is receive-only and doesn't send responses to email. "
            "Responses are delivered through other providers (e.g., Discord) via the event system."
        )

    @property
    def is_running(self) -> bool:
        """Check if provider is running.

        Backward compatibility alias for Provider.running property.

        Returns:
            True if provider is running
        """
        return self._running
