"""Pytest configuration and fixtures for MyPalClara tests."""

import sys
from pathlib import Path

import pytest

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


@pytest.fixture
def sample_event():
    """Create a sample Event for testing."""
    from mypalclara.models.events import ChannelMode, Event, EventType

    return Event(
        id="test-123",
        type=EventType.MESSAGE,
        user_id="user-456",
        user_name="TestUser",
        channel_id="channel-789",
        content="Hello Clara!",
        is_dm=True,
        mentioned=False,
        reply_to_clara=False,
        channel_mode=ChannelMode.CONVERSATIONAL,
    )


@pytest.fixture
def sample_quick_context():
    """Create a sample QuickContext for testing."""
    from mypalclara.models.state import QuickContext

    return QuickContext(
        user_id="user-456",
        user_name="TestUser",
        identity_facts=["name: TestUser", "timezone: UTC"],
        session={"last_topic": "greeting"},
        last_interaction="2024-01-01T00:00:00",
    )


@pytest.fixture
def sample_memory_context():
    """Create a sample MemoryContext for testing."""
    from mypalclara.models.state import MemoryContext

    return MemoryContext(
        user_id="user-456",
        user_name="TestUser",
        identity_facts=["name: TestUser"],
        session={},
        working_memories=[{"content": "Recent chat", "score": 0.5}],
        retrieved_memories=[],
        project_context=None,
    )
