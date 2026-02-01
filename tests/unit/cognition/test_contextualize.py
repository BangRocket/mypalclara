"""Tests for the cognition Contextualizer module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clara_core.cognition.contextualize import (
    Contextualizer,
    ContextualizerConfig,
    SessionInfo,
    create_contextualizer,
)
from clara_core.cognition.types import (
    CognitionEvent,
    ContextBundle,
    EventMetadata,
    EventType,
)


def make_event(
    content: str,
    user_id: str = "user-123",
    channel_id: str = "channel-456",
    is_dm: bool = False,
) -> CognitionEvent:
    """Helper to create a message event."""
    return CognitionEvent(
        type=EventType.MESSAGE,
        payload={"content": content, "is_dm": is_dm},
        metadata=EventMetadata(
            user_id=user_id,
            channel_id=channel_id,
            request_id="req-test",
        ),
    )


@pytest.fixture
def mock_memory_manager():
    """Create a mock MemoryManager for testing."""
    mm = MagicMock()

    # Mock get_or_create_session
    mock_session = MagicMock()
    mock_session.id = "session-123"
    mock_session.project_id = "project-456"
    mock_session.session_summary = "Previous conversation summary"
    mm.get_or_create_session.return_value = mock_session

    # Mock get_recent_messages
    mock_msg1 = MagicMock()
    mock_msg1.role = "user"
    mock_msg1.content = "Hello"
    mock_msg2 = MagicMock()
    mock_msg2.role = "assistant"
    mock_msg2.content = "Hi there!"
    mm.get_recent_messages.return_value = [mock_msg1, mock_msg2]

    # Mock get_message_count
    mm.get_message_count.return_value = 5

    # Mock fetch_mem0_context
    mm.fetch_mem0_context.return_value = (
        ["User likes Python", "User is a developer"],  # user_mems
        ["Project uses FastAPI"],  # proj_mems
        [{"source": "user", "relationship": "likes", "destination": "Python"}],  # graph
    )

    # Mock fetch_emotional_context
    mm.fetch_emotional_context.return_value = [
        {
            "memory": "User seemed stressed about deadline",
            "arc": "declining",
            "energy": "stressed",
        }
    ]

    # Mock build_prompt
    mm.build_prompt.return_value = [
        {"role": "system", "content": "You are Clara..."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "What's new?"},
    ]

    return mm


@pytest.fixture
def mock_db_context():
    """Create a mock database context manager."""
    mock_db = MagicMock()
    return mock_db


class TestContextualizerBasic:
    """Basic tests for Contextualizer initialization and configuration."""

    def test_default_config(self):
        """Contextualizer should use default config if none provided."""
        ctx = Contextualizer()
        assert ctx.config.fetch_user_memories is True
        assert ctx.config.fetch_emotional_context is True
        assert ctx.config.max_memories == 50

    def test_custom_config(self):
        """Contextualizer should accept custom configuration."""
        config = ContextualizerConfig(
            fetch_user_memories=False,
            max_memories=25,
        )
        ctx = Contextualizer(config=config)
        assert ctx.config.fetch_user_memories is False
        assert ctx.config.max_memories == 25

    def test_factory_function(self):
        """create_contextualizer should create configured instance."""
        ctx = create_contextualizer(
            fetch_emotional=False,
            fetch_graph=False,
        )
        assert ctx.config.fetch_emotional_context is False
        assert ctx.config.fetch_graph_relations is False


class TestContextualizeMethod:
    """Tests for the main contextualize() method."""

    @pytest.mark.asyncio
    async def test_builds_valid_context_bundle(self, mock_memory_manager):
        """contextualize should return a valid ContextBundle."""
        ctx = Contextualizer(memory_manager=mock_memory_manager)
        event = make_event("What's new?")

        with patch("db.SessionLocal") as mock_session_local:
            mock_session_local.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_session_local.return_value.__exit__ = MagicMock(return_value=False)

            bundle = await ctx.contextualize(event)

        assert isinstance(bundle, ContextBundle)
        assert bundle.user_id == "user-123"
        assert bundle.channel_id == "channel-456"
        assert len(bundle.messages) > 0

    @pytest.mark.asyncio
    async def test_fetches_memories(self, mock_memory_manager):
        """contextualize should fetch memories from mem0."""
        ctx = Contextualizer(memory_manager=mock_memory_manager)
        event = make_event("Tell me about Python")

        with patch("db.SessionLocal") as mock_session_local:
            mock_session_local.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_session_local.return_value.__exit__ = MagicMock(return_value=False)

            bundle = await ctx.contextualize(event)

        # Verify fetch_mem0_context was called
        mock_memory_manager.fetch_mem0_context.assert_called_once()

        # Verify memories are in the bundle
        assert "User likes Python" in bundle.memories
        assert "Project uses FastAPI" in bundle.project_memories

    @pytest.mark.asyncio
    async def test_emotional_state_extracted(self, mock_memory_manager):
        """contextualize should extract emotional state from context."""
        ctx = Contextualizer(memory_manager=mock_memory_manager)
        event = make_event("How's it going?")

        with patch("db.SessionLocal") as mock_session_local:
            mock_session_local.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_session_local.return_value.__exit__ = MagicMock(return_value=False)

            bundle = await ctx.contextualize(event)

        # Should extract "stressed" from the mock emotional context
        assert bundle.emotional_state == "stressed"

    @pytest.mark.asyncio
    async def test_session_messages_included(self, mock_memory_manager):
        """contextualize should include session messages."""
        ctx = Contextualizer(memory_manager=mock_memory_manager)
        event = make_event("Continue our conversation")

        with patch("db.SessionLocal") as mock_session_local:
            mock_session_local.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_session_local.return_value.__exit__ = MagicMock(return_value=False)

            bundle = await ctx.contextualize(event)

        # Should have session messages from mock
        assert len(bundle.session_messages) == 2
        assert bundle.session_messages[0]["role"] == "user"
        assert bundle.session_messages[0]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_dm_context_id_format(self, mock_memory_manager):
        """DM events should use dm-{user_id} context format."""
        ctx = Contextualizer(memory_manager=mock_memory_manager)
        event = make_event("Hello", is_dm=True)

        with patch("db.SessionLocal") as mock_session_local:
            mock_session_local.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_session_local.return_value.__exit__ = MagicMock(return_value=False)

            await ctx.contextualize(event)

        # Verify context_id format
        call_args = mock_memory_manager.get_or_create_session.call_args
        assert call_args.kwargs["context_id"] == "dm-user-123"

    @pytest.mark.asyncio
    async def test_channel_context_id_format(self, mock_memory_manager):
        """Channel events should use channel-{channel_id} context format."""
        ctx = Contextualizer(memory_manager=mock_memory_manager)
        event = make_event("Hello", is_dm=False, channel_id="general-789")

        with patch("db.SessionLocal") as mock_session_local:
            mock_session_local.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_session_local.return_value.__exit__ = MagicMock(return_value=False)

            await ctx.contextualize(event)

        # Verify context_id format
        call_args = mock_memory_manager.get_or_create_session.call_args
        assert call_args.kwargs["context_id"] == "channel-general-789"


class TestSessionInfo:
    """Tests for the SessionInfo dataclass."""

    def test_default_values(self):
        """SessionInfo should have sensible defaults."""
        info = SessionInfo()
        assert info.session_id == ""
        assert info.is_new_session is False
        assert info.message_count == 0
        assert info.recent_messages == []

    def test_populated_values(self):
        """SessionInfo should hold provided values."""
        info = SessionInfo(
            session_id="sess-123",
            user_id="user-456",
            is_new_session=True,
            message_count=10,
            recent_messages=[{"role": "user", "content": "Hi"}],
        )
        assert info.session_id == "sess-123"
        assert info.is_new_session is True
        assert info.message_count == 10


class TestErrorHandling:
    """Tests for error handling in Contextualizer."""

    @pytest.mark.asyncio
    async def test_memory_fetch_error_returns_empty(self, mock_memory_manager):
        """Memory fetch errors should return empty lists, not crash."""
        mock_memory_manager.fetch_mem0_context.side_effect = Exception("mem0 error")

        ctx = Contextualizer(memory_manager=mock_memory_manager)
        event = make_event("Hello")

        with patch("db.SessionLocal") as mock_session_local:
            mock_session_local.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_session_local.return_value.__exit__ = MagicMock(return_value=False)

            bundle = await ctx.contextualize(event)

        # Should still return a bundle, just with empty memories
        assert bundle.memories == []
        assert bundle.project_memories == []

    @pytest.mark.asyncio
    async def test_emotional_fetch_error_returns_neutral(self, mock_memory_manager):
        """Emotional context errors should return neutral state."""
        mock_memory_manager.fetch_emotional_context.side_effect = Exception("error")

        ctx = Contextualizer(memory_manager=mock_memory_manager)
        event = make_event("Hello")

        with patch("db.SessionLocal") as mock_session_local:
            mock_session_local.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_session_local.return_value.__exit__ = MagicMock(return_value=False)

            bundle = await ctx.contextualize(event)

        # Should default to neutral on error
        assert bundle.emotional_state == "neutral"

    @pytest.mark.asyncio
    async def test_session_error_returns_minimal_info(self, mock_memory_manager):
        """Session errors should return minimal SessionInfo."""
        ctx = Contextualizer(memory_manager=mock_memory_manager)
        event = make_event("Hello")

        # Make get_db raise an error
        with patch("db.SessionLocal") as mock_session_local:
            mock_session_local.side_effect = Exception("DB connection error")

            # contextualize should still work, just with empty session
            bundle = await ctx.contextualize(event)

        # Should still have user_id and channel_id at minimum
        assert bundle.user_id == "user-123"
        assert bundle.channel_id == "channel-456"


class TestConfigDisabled:
    """Tests for disabled context fetching."""

    @pytest.mark.asyncio
    async def test_memories_disabled(self, mock_memory_manager):
        """Disabling memory fetch should skip mem0 call."""
        config = ContextualizerConfig(fetch_user_memories=False)
        ctx = Contextualizer(config=config, memory_manager=mock_memory_manager)
        event = make_event("Hello")

        with patch("db.SessionLocal") as mock_session_local:
            mock_session_local.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_session_local.return_value.__exit__ = MagicMock(return_value=False)

            bundle = await ctx.contextualize(event)

        # fetch_mem0_context should not be called
        mock_memory_manager.fetch_mem0_context.assert_not_called()
        assert bundle.memories == []

    @pytest.mark.asyncio
    async def test_emotional_context_disabled(self, mock_memory_manager):
        """Disabling emotional context should skip fetch."""
        config = ContextualizerConfig(fetch_emotional_context=False)
        ctx = Contextualizer(config=config, memory_manager=mock_memory_manager)
        event = make_event("Hello")

        with patch("db.SessionLocal") as mock_session_local:
            mock_session_local.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_session_local.return_value.__exit__ = MagicMock(return_value=False)

            bundle = await ctx.contextualize(event)

        # fetch_emotional_context should not be called
        mock_memory_manager.fetch_emotional_context.assert_not_called()
        assert bundle.emotional_state == "neutral"
