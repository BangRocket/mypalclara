"""Tests for email provider."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from adapters.email.monitor import EmailInfo
from adapters.email.provider import EmailProvider
from gateway.events import Event, EventType, on, reset_event_emitter


@pytest.fixture(autouse=True)
def reset_emitter():
    """Reset global event emitter between tests."""
    yield
    reset_event_emitter()


@pytest.fixture
def mock_email_info():
    """Create mock EmailInfo."""
    return EmailInfo(
        uid="123",
        from_addr="sender@example.com",
        subject="Test Subject",
        date="Mon, 27 Jan 2026 10:00:00 +0000",
        preview="This is a test email...",
        is_read=False,
    )


class TestEmailProvider:
    """Tests for EmailProvider."""

    @pytest.mark.asyncio
    async def test_provider_initialization(self):
        """Test provider initializes correctly."""
        provider = EmailProvider(check_interval=30)
        assert provider.check_interval == 30
        assert provider.is_running is False

    @pytest.mark.asyncio
    async def test_start_without_credentials_warns(self):
        """Test provider warns when email not configured."""
        provider = EmailProvider()

        with patch.dict("os.environ", {}, clear=True):
            await provider.start()

        # Should not be running without credentials
        assert provider.is_running is False

    @pytest.mark.asyncio
    async def test_emit_email_alert(self, mock_email_info):
        """Test email alert event emission."""
        provider = EmailProvider(notify_user_id="discord-123456")
        received_events = []

        async def capture_event(event: Event):
            received_events.append(event)

        on(EventType.MESSAGE_RECEIVED, capture_event)

        await provider._emit_email_alert(mock_email_info)

        assert len(received_events) == 1
        event = received_events[0]
        assert event.type == EventType.MESSAGE_RECEIVED
        assert event.platform == "email"
        assert event.data["from"] == "sender@example.com"
        assert event.data["subject"] == "Test Subject"
        assert event.data["provider"] == "email"

    @pytest.mark.asyncio
    async def test_check_and_emit_with_new_emails(self, mock_email_info):
        """Test new emails trigger events."""
        provider = EmailProvider(notify_user_id="discord-123456")
        received_events = []

        async def capture_event(event: Event):
            received_events.append(event)

        on(EventType.MESSAGE_RECEIVED, capture_event)

        # Mock the monitor to return emails
        provider.monitor.get_new_emails_async = AsyncMock(
            return_value=([mock_email_info], None)
        )

        await provider._check_and_emit()

        assert len(received_events) == 1
        assert provider._emails_processed == 1

    @pytest.mark.asyncio
    async def test_check_and_emit_with_error(self):
        """Test error handling during check."""
        provider = EmailProvider()

        # Mock monitor to return error
        provider.monitor.get_new_emails_async = AsyncMock(
            return_value=([], "Connection failed")
        )

        await provider._check_and_emit()

        assert provider._last_error == "Connection failed"

    @pytest.mark.asyncio
    async def test_check_and_emit_no_emails(self):
        """Test no events emitted when no new emails."""
        provider = EmailProvider(notify_user_id="discord-123456")
        received_events = []

        async def capture_event(event: Event):
            received_events.append(event)

        on(EventType.MESSAGE_RECEIVED, capture_event)

        # Mock monitor to return empty list
        provider.monitor.get_new_emails_async = AsyncMock(return_value=([], None))

        await provider._check_and_emit()

        assert len(received_events) == 0
        assert provider._emails_processed == 0

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test statistics reporting."""
        provider = EmailProvider(check_interval=60)
        provider._running = True
        provider._started_at = datetime.now()
        provider._emails_processed = 5

        stats = provider.get_stats()

        assert stats["running"] is True
        assert stats["emails_processed"] == 5
        assert stats["check_interval"] == 60
        assert stats["uptime_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_get_stats_not_running(self):
        """Test statistics when provider is not running."""
        provider = EmailProvider(check_interval=30)

        stats = provider.get_stats()

        assert stats["running"] is False
        assert stats["started_at"] is None
        assert stats["uptime_seconds"] is None
        assert stats["emails_processed"] == 0

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        """Test stop is safe when provider not running."""
        provider = EmailProvider()

        # Should not raise
        await provider.stop()

        assert provider.is_running is False

    @pytest.mark.asyncio
    async def test_multiple_emails_emit_multiple_events(self, mock_email_info):
        """Test multiple emails trigger multiple events."""
        provider = EmailProvider(notify_user_id="discord-123456")
        received_events = []

        async def capture_event(event: Event):
            received_events.append(event)

        on(EventType.MESSAGE_RECEIVED, capture_event)

        # Create multiple mock emails
        email1 = mock_email_info
        email2 = EmailInfo(
            uid="124",
            from_addr="another@example.com",
            subject="Second Email",
            date="Mon, 27 Jan 2026 11:00:00 +0000",
            preview="Another test...",
            is_read=False,
        )

        provider.monitor.get_new_emails_async = AsyncMock(
            return_value=([email1, email2], None)
        )

        await provider._check_and_emit()

        assert len(received_events) == 2
        assert provider._emails_processed == 2
        assert received_events[0].data["subject"] == "Test Subject"
        assert received_events[1].data["subject"] == "Second Email"
