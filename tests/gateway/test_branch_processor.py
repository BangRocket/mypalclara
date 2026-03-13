"""Tests for branch-aware processor functionality.

Tests:
- MessageRequest accepts branch_id
- MessageRequest branch_id is optional (defaults to None)
- _get_branch_context returns correct messages
- _store_branch_message creates and returns message ID
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from mypalclara.gateway.processor import MessageProcessor
from mypalclara.gateway.protocol import ChannelInfo, MessageRequest, UserInfo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_request(
    content: str = "Hello",
    branch_id: str | None = None,
    channel_type: str = "dm",
    channel_id: str = "channel-1",
    user_name: str = "TestUser",
) -> MessageRequest:
    """Create a test message request."""
    return MessageRequest(
        id=f"req-{uuid.uuid4().hex[:8]}",
        user=UserInfo(
            id="user-1",
            platform_id="user-1",
            name=user_name,
            display_name=user_name,
        ),
        channel=ChannelInfo(
            id=channel_id,
            type=channel_type,
        ),
        content=content,
        branch_id=branch_id,
    )


# ---------------------------------------------------------------------------
# Protocol tests
# ---------------------------------------------------------------------------


class TestMessageRequestBranchId:
    """Verify branch_id field on MessageRequest."""

    def test_branch_id_accepted(self):
        """MessageRequest should accept a branch_id."""
        req = make_request(branch_id="branch-abc-123")
        assert req.branch_id == "branch-abc-123"

    def test_branch_id_defaults_to_none(self):
        """MessageRequest branch_id should default to None when not provided."""
        req = make_request()
        assert req.branch_id is None

    def test_branch_id_serialization(self):
        """branch_id should round-trip through JSON serialization."""
        req = make_request(branch_id="branch-xyz")
        data = req.model_dump()
        assert data["branch_id"] == "branch-xyz"

        restored = MessageRequest.model_validate(data)
        assert restored.branch_id == "branch-xyz"

    def test_branch_id_none_serialization(self):
        """None branch_id should round-trip through JSON serialization."""
        req = make_request()
        data = req.model_dump()
        assert data["branch_id"] is None

        restored = MessageRequest.model_validate(data)
        assert restored.branch_id is None


# ---------------------------------------------------------------------------
# Processor method tests (unit-level, mocked DB)
# ---------------------------------------------------------------------------


@pytest.fixture
def processor():
    """Create a processor instance (not fully initialized)."""
    return MessageProcessor()


class TestGetBranchContext:
    """Tests for _get_branch_context."""

    def test_returns_empty_for_missing_branch(self, processor):
        """Should return empty list when branch does not exist."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch("mypalclara.gateway.processor.SessionLocal", return_value=mock_db):
            result = processor._get_branch_context("nonexistent-branch", "user-1")

        assert result == []

    def test_returns_messages_for_existing_branch(self, processor):
        """Should return messages from the branch in correct format."""
        # Create mock branch (no parent)
        mock_branch = MagicMock()
        mock_branch.id = "branch-1"
        mock_branch.parent_branch_id = None

        # Create mock messages
        mock_msg_1 = MagicMock()
        mock_msg_1.role = "user"
        mock_msg_1.content = "Hello"
        mock_msg_1.created_at = None

        mock_msg_2 = MagicMock()
        mock_msg_2.role = "assistant"
        mock_msg_2.content = "Hi there!"
        mock_msg_2.created_at = None

        mock_db = MagicMock()
        # First query: find branch
        mock_db.query.return_value.filter.return_value.first.return_value = mock_branch
        # Second query: branch messages
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
            mock_msg_1,
            mock_msg_2,
        ]

        with patch("mypalclara.gateway.processor.SessionLocal", return_value=mock_db):
            result = processor._get_branch_context("branch-1", "user-1")

        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "Hello"}
        assert result[1] == {"role": "assistant", "content": "Hi there!"}

    def test_limits_message_count(self, processor):
        """Should respect the limit parameter."""
        mock_branch = MagicMock()
        mock_branch.id = "branch-1"
        mock_branch.parent_branch_id = None

        # Create more messages than the limit
        mock_messages = []
        for i in range(10):
            msg = MagicMock()
            msg.role = "user" if i % 2 == 0 else "assistant"
            msg.content = f"Message {i}"
            msg.created_at = None
            mock_messages.append(msg)

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_branch
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = mock_messages

        with patch("mypalclara.gateway.processor.SessionLocal", return_value=mock_db):
            result = processor._get_branch_context("branch-1", "user-1", limit=5)

        # Should return only the last 5 messages
        assert len(result) == 5
        assert result[0]["content"] == "Message 5"
        assert result[4]["content"] == "Message 9"


class TestStoreBranchMessage:
    """Tests for _store_branch_message."""

    def test_creates_message_and_returns_id(self, processor):
        """Should create a BranchMessage and return its ID."""
        mock_msg = MagicMock()
        mock_msg.id = "msg-abc-123"

        mock_db = MagicMock()
        # Simulate refresh setting the id
        mock_db.refresh = MagicMock(side_effect=lambda m: setattr(m, "id", "msg-abc-123"))

        with patch("mypalclara.gateway.processor.SessionLocal", return_value=mock_db):
            with patch("mypalclara.gateway.processor.BranchMessage") as MockBM:
                mock_instance = MagicMock()
                mock_instance.id = "msg-abc-123"
                MockBM.return_value = mock_instance

                result = processor._store_branch_message(
                    branch_id="branch-1",
                    user_id="user-1",
                    role="user",
                    content="Hello from branch",
                )

        assert result == "msg-abc-123"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_passes_attachments_and_tool_calls(self, processor):
        """Should forward optional attachments and tool_calls."""
        mock_db = MagicMock()

        with patch("mypalclara.gateway.processor.SessionLocal", return_value=mock_db):
            with patch("mypalclara.gateway.processor.BranchMessage") as MockBM:
                mock_instance = MagicMock()
                mock_instance.id = "msg-xyz"
                MockBM.return_value = mock_instance

                processor._store_branch_message(
                    branch_id="branch-1",
                    user_id="user-1",
                    role="assistant",
                    content="Reply",
                    attachments='[{"type": "image"}]',
                    tool_calls='[{"name": "search"}]',
                )

                MockBM.assert_called_once_with(
                    branch_id="branch-1",
                    user_id="user-1",
                    role="assistant",
                    content="Reply",
                    attachments='[{"type": "image"}]',
                    tool_calls='[{"name": "search"}]',
                )

    def test_rolls_back_on_error(self, processor):
        """Should rollback and re-raise on database error."""
        mock_db = MagicMock()
        mock_db.commit.side_effect = Exception("DB error")

        with patch("mypalclara.gateway.processor.SessionLocal", return_value=mock_db):
            with patch("mypalclara.gateway.processor.BranchMessage") as MockBM:
                MockBM.return_value = MagicMock()

                with pytest.raises(Exception, match="DB error"):
                    processor._store_branch_message(
                        branch_id="branch-1",
                        user_id="user-1",
                        role="user",
                        content="Boom",
                    )

        mock_db.rollback.assert_called_once()
        mock_db.close.assert_called_once()
