"""Tests for the loopback adapter."""

import asyncio

import pytest

from mypalclara.gateway.loopback import LoopbackAdapter
from mypalclara.gateway.protocol import MessageRequest


@pytest.fixture
def adapter():
    return LoopbackAdapter()


class TestLoopbackAdapter:
    """Tests for LoopbackAdapter."""

    @pytest.mark.asyncio
    async def test_send_creates_and_dispatches_message_request(self, adapter):
        """send() should build a MessageRequest and call the processor."""
        received = []

        async def fake_processor(request):
            received.append(request)
            return "ok"

        adapter.set_processor(fake_processor)
        await adapter.send("hello world", user_id="user-1", channel_id="ch-1", source="test")

        assert len(received) == 1
        req = received[0]
        assert isinstance(req, MessageRequest)
        assert req.content == "hello world"
        assert req.user.id == "user-1"
        assert req.user.platform_id == "user-1"
        assert req.user.name == "test"
        assert req.channel.id == "ch-1"
        assert req.channel.type == "dm"
        assert req.metadata["source"] == "test"
        assert req.metadata["loopback"] is True
        assert req.id.startswith("loopback-")

    @pytest.mark.asyncio
    async def test_send_and_wait_returns_processor_response(self, adapter):
        """send_and_wait() should return the processor's response string."""

        async def fake_processor(request):
            return f"Processed: {request.content}"

        adapter.set_processor(fake_processor)
        result = await adapter.send_and_wait("ping", source="scheduler")

        assert result == "Processed: ping"

    @pytest.mark.asyncio
    async def test_send_without_processor_does_not_raise(self, adapter):
        """send() with no processor set should not raise."""
        # No processor set — should handle gracefully
        await adapter.send("ignored message")

    @pytest.mark.asyncio
    async def test_send_and_wait_without_processor_returns_empty(self, adapter):
        """send_and_wait() with no processor should return empty string."""
        result = await adapter.send_and_wait("ignored")
        assert result == ""

    @pytest.mark.asyncio
    async def test_send_and_wait_timeout(self, adapter):
        """send_and_wait() should raise TimeoutError if processor is too slow."""

        async def slow_processor(request):
            await asyncio.sleep(10)
            return "too late"

        adapter.set_processor(slow_processor)
        with pytest.raises(TimeoutError):
            await adapter.send_and_wait("hurry", timeout=0.1)

    @pytest.mark.asyncio
    async def test_tier_override_passed_through(self, adapter):
        """tier_override should be set on the MessageRequest."""
        received = []

        async def fake_processor(request):
            received.append(request)
            return "ok"

        adapter.set_processor(fake_processor)
        await adapter.send("test", tier="high")

        assert received[0].tier_override == "high"

    def test_build_request_structure(self, adapter):
        """_build_request should produce a valid MessageRequest."""
        req = adapter._build_request(
            content="test content",
            user_id="sys",
            channel_id="internal",
            source="cron",
            tier="low",
        )
        assert isinstance(req, MessageRequest)
        assert req.content == "test content"
        assert req.tier_override == "low"
        assert req.channel.name == "internal"
        assert req.user.display_name == "cron"
