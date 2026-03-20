"""Tests for memory injection as synthetic tool results."""

from mypalclara.core.llm.messages import (
    AssistantMessage,
    SystemMessage,
    ToolResultMessage,
    UserMessage,
)
from mypalclara.gateway.processor import inject_memory_as_tool_results


class TestInjectMemoryAsToolResults:
    """Tests for inject_memory_as_tool_results()."""

    def test_empty_memories_returns_unchanged(self):
        """Empty memories list should return messages unchanged (noop)."""
        messages = [
            SystemMessage(content="You are Clara."),
            UserMessage(content="Hello!"),
        ]
        result = inject_memory_as_tool_results(messages, [], "user_memories")
        assert result == messages
        # Must not mutate original
        assert result is not messages or len(result) == len(messages)

    def test_nonempty_memories_creates_tool_call_pair(self):
        """Non-empty memories should create an AssistantMessage with ToolCall + ToolResultMessage."""
        messages = [
            SystemMessage(content="You are Clara."),
            UserMessage(content="Hello!"),
        ]
        memories = ["User prefers dark mode", "User's name is Joshua"]
        result = inject_memory_as_tool_results(messages, memories, "user_memories")

        # Should have 2 extra messages (assistant + tool result)
        assert len(result) == len(messages) + 2

        # Find the injected pair
        assistant_msg = result[-3]  # before last user message
        tool_result_msg = result[-2]

        assert isinstance(assistant_msg, AssistantMessage)
        assert assistant_msg.content is None
        assert len(assistant_msg.tool_calls) == 1
        tc = assistant_msg.tool_calls[0]
        assert tc.id == "synthetic_user_memories"
        assert tc.name == "search_memory"
        assert tc.arguments == {"query": "relevant context"}

        assert isinstance(tool_result_msg, ToolResultMessage)
        assert tool_result_msg.tool_call_id == "synthetic_user_memories"
        assert "User prefers dark mode" in tool_result_msg.content
        assert "User's name is Joshua" in tool_result_msg.content

    def test_injected_pair_before_last_message(self):
        """The synthetic pair must appear just before the last (user) message."""
        messages = [
            SystemMessage(content="System prompt"),
            AssistantMessage(content="Hi there!"),
            UserMessage(content="What do you know about me?"),
        ]
        memories = ["Likes cats"]
        result = inject_memory_as_tool_results(messages, memories, "proj_memories")

        # Last message should still be the user message
        assert isinstance(result[-1], UserMessage)
        assert result[-1].content == "What do you know about me?"

        # Second-to-last should be tool result
        assert isinstance(result[-2], ToolResultMessage)
        assert result[-2].tool_call_id == "synthetic_proj_memories"

        # Third-to-last should be assistant with tool call
        assert isinstance(result[-3], AssistantMessage)
        assert result[-3].tool_calls[0].id == "synthetic_proj_memories"

        # First messages unchanged
        assert result[0] == messages[0]
        assert result[1] == messages[1]

    def test_does_not_mutate_input(self):
        """The original messages list must not be modified."""
        messages = [
            SystemMessage(content="System"),
            UserMessage(content="Hi"),
        ]
        original_len = len(messages)
        inject_memory_as_tool_results(messages, ["some memory"], "user_memories")
        assert len(messages) == original_len

    def test_memory_content_formatting(self):
        """Memories should be formatted with source header and bullet points."""
        messages = [UserMessage(content="test")]
        memories = ["Fact A", "Fact B", "Fact C"]
        result = inject_memory_as_tool_results(messages, memories, "user_memories")

        tool_result = result[-2]
        assert isinstance(tool_result, ToolResultMessage)
        assert tool_result.content == "[user_memories]\n- Fact A\n- Fact B\n- Fact C"
