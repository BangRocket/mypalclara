"""Tests for the typed message format (clara_core.llm.messages)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from clara_core.llm.messages import (
    AssistantMessage,
    ContentPart,
    ContentPartType,
    Message,
    SystemMessage,
    ToolResultMessage,
    UserMessage,
    message_from_dict,
    messages_from_dicts,
)
from clara_core.llm.tools.response import ToolCall, ToolResponse

# =============================================================================
# SystemMessage
# =============================================================================


class TestSystemMessage:
    def test_to_dict(self):
        msg = SystemMessage(content="You are helpful")
        assert msg.to_dict() == {"role": "system", "content": "You are helpful"}

    def test_from_dict_roundtrip(self):
        msg = SystemMessage(content="Be concise")
        result = message_from_dict(msg.to_dict())
        assert result == msg

    def test_equality(self):
        assert SystemMessage(content="a") == SystemMessage(content="a")
        assert SystemMessage(content="a") != SystemMessage(content="b")


# =============================================================================
# UserMessage
# =============================================================================


class TestUserMessage:
    def test_plain_text_to_dict(self):
        msg = UserMessage(content="Hello")
        assert msg.to_dict() == {"role": "user", "content": "Hello"}

    def test_plain_text_roundtrip(self):
        msg = UserMessage(content="Hello world")
        result = message_from_dict(msg.to_dict())
        assert result == msg

    def test_multimodal_to_dict(self):
        parts = [
            ContentPart(type=ContentPartType.TEXT, text="Look at this"),
            ContentPart(
                type=ContentPartType.IMAGE_BASE64,
                media_type="image/png",
                data="abc123",
            ),
        ]
        msg = UserMessage(content="Look at this", parts=parts)
        d = msg.to_dict()
        assert d["role"] == "user"
        assert isinstance(d["content"], list)
        assert len(d["content"]) == 2
        assert d["content"][0] == {"type": "text", "text": "Look at this"}
        assert d["content"][1]["type"] == "image_url"
        assert "data:image/png;base64,abc123" in d["content"][1]["image_url"]["url"]

    def test_multimodal_roundtrip(self):
        parts = [
            ContentPart(type=ContentPartType.TEXT, text="Look at this"),
            ContentPart(
                type=ContentPartType.IMAGE_BASE64,
                media_type="image/png",
                data="abc123",
            ),
        ]
        msg = UserMessage(content="Look at this", parts=parts)
        result = message_from_dict(msg.to_dict())
        assert isinstance(result, UserMessage)
        assert len(result.parts) == 2
        assert result.parts[0].type == ContentPartType.TEXT
        assert result.parts[0].text == "Look at this"
        assert result.parts[1].type == ContentPartType.IMAGE_BASE64
        assert result.parts[1].media_type == "image/png"
        assert result.parts[1].data == "abc123"

    def test_image_url_part(self):
        parts = [
            ContentPart(type=ContentPartType.IMAGE_URL, url="https://example.com/img.png"),
        ]
        msg = UserMessage(content="", parts=parts)
        d = msg.to_dict()
        assert d["content"][0]["type"] == "image_url"
        assert d["content"][0]["image_url"]["url"] == "https://example.com/img.png"

    def test_image_url_roundtrip(self):
        parts = [
            ContentPart(type=ContentPartType.IMAGE_URL, url="https://example.com/img.png"),
        ]
        msg = UserMessage(content="", parts=parts)
        result = message_from_dict(msg.to_dict())
        assert isinstance(result, UserMessage)
        assert result.parts[0].type == ContentPartType.IMAGE_URL
        assert result.parts[0].url == "https://example.com/img.png"

    def test_text_property_plain(self):
        msg = UserMessage(content="Hello")
        assert msg.text == "Hello"

    def test_text_property_from_parts(self):
        parts = [
            ContentPart(type=ContentPartType.TEXT, text="First"),
            ContentPart(type=ContentPartType.IMAGE_BASE64, media_type="image/png", data="x"),
            ContentPart(type=ContentPartType.TEXT, text="Second"),
        ]
        msg = UserMessage(content="fallback", parts=parts)
        assert msg.text == "First Second"

    def test_is_multimodal_false(self):
        msg = UserMessage(content="plain text")
        assert msg.is_multimodal is False

    def test_is_multimodal_text_parts_only(self):
        parts = [ContentPart(type=ContentPartType.TEXT, text="just text")]
        msg = UserMessage(content="just text", parts=parts)
        assert msg.is_multimodal is False

    def test_is_multimodal_true(self):
        parts = [
            ContentPart(type=ContentPartType.TEXT, text="with image"),
            ContentPart(type=ContentPartType.IMAGE_BASE64, media_type="image/png", data="x"),
        ]
        msg = UserMessage(content="with image", parts=parts)
        assert msg.is_multimodal is True


# =============================================================================
# AssistantMessage
# =============================================================================


class TestAssistantMessage:
    def test_plain_to_dict(self):
        msg = AssistantMessage(content="Hello there!")
        d = msg.to_dict()
        assert d == {"role": "assistant", "content": "Hello there!"}
        assert "tool_calls" not in d

    def test_plain_roundtrip(self):
        msg = AssistantMessage(content="Hello there!")
        result = message_from_dict(msg.to_dict())
        assert result == msg

    def test_with_tool_calls_to_dict(self):
        tc = ToolCall(id="call_1", name="web_search", arguments={"query": "test"})
        msg = AssistantMessage(content="Let me search", tool_calls=[tc])
        d = msg.to_dict()
        assert d["role"] == "assistant"
        assert d["content"] == "Let me search"
        assert len(d["tool_calls"]) == 1
        assert d["tool_calls"][0]["function"]["name"] == "web_search"

    def test_with_tool_calls_roundtrip(self):
        tc = ToolCall(id="call_1", name="web_search", arguments={"query": "test"})
        msg = AssistantMessage(content="Let me search", tool_calls=[tc])
        result = message_from_dict(msg.to_dict())
        assert isinstance(result, AssistantMessage)
        assert result.content == "Let me search"
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "web_search"
        assert result.tool_calls[0].id == "call_1"
        assert result.tool_calls[0].arguments == {"query": "test"}

    def test_none_content(self):
        msg = AssistantMessage(content=None)
        d = msg.to_dict()
        assert d["content"] is None

    def test_none_content_roundtrip(self):
        msg = AssistantMessage(content=None)
        result = message_from_dict(msg.to_dict())
        assert isinstance(result, AssistantMessage)
        assert result.content is None


# =============================================================================
# ToolResultMessage
# =============================================================================


class TestToolResultMessage:
    def test_to_dict(self):
        msg = ToolResultMessage(tool_call_id="call_1", content="42")
        assert msg.to_dict() == {
            "role": "tool",
            "tool_call_id": "call_1",
            "content": "42",
        }

    def test_roundtrip(self):
        msg = ToolResultMessage(tool_call_id="call_1", content="result text")
        result = message_from_dict(msg.to_dict())
        assert result == msg


# =============================================================================
# message_from_dict edge cases
# =============================================================================


class TestMessageFromDict:
    def test_unknown_role_raises(self):
        with pytest.raises(ValueError, match="Unknown message role"):
            message_from_dict({"role": "potato", "content": "wat"})

    def test_missing_role_raises(self):
        with pytest.raises(ValueError, match="Unknown message role"):
            message_from_dict({"content": "no role"})

    def test_messages_from_dicts(self):
        dicts = [
            {"role": "system", "content": "Be helpful"},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
        msgs = messages_from_dicts(dicts)
        assert len(msgs) == 3
        assert isinstance(msgs[0], SystemMessage)
        assert isinstance(msgs[1], UserMessage)
        assert isinstance(msgs[2], AssistantMessage)


# =============================================================================
# ContentPart
# =============================================================================


class TestContentPart:
    def test_text_to_dict(self):
        part = ContentPart(type=ContentPartType.TEXT, text="Hello")
        assert part.to_dict() == {"type": "text", "text": "Hello"}

    def test_image_base64_to_dict(self):
        part = ContentPart(
            type=ContentPartType.IMAGE_BASE64,
            media_type="image/jpeg",
            data="base64data",
        )
        d = part.to_dict()
        assert d["type"] == "image_url"
        assert d["image_url"]["url"] == "data:image/jpeg;base64,base64data"

    def test_image_url_to_dict(self):
        part = ContentPart(type=ContentPartType.IMAGE_URL, url="https://example.com/img.png")
        d = part.to_dict()
        assert d["type"] == "image_url"
        assert d["image_url"]["url"] == "https://example.com/img.png"

    def test_from_dict_text(self):
        part = ContentPart.from_dict({"type": "text", "text": "Hello"})
        assert part.type == ContentPartType.TEXT
        assert part.text == "Hello"

    def test_from_dict_base64_data_url(self):
        part = ContentPart.from_dict(
            {
                "type": "image_url",
                "image_url": {"url": "data:image/png;base64,abc123"},
            }
        )
        assert part.type == ContentPartType.IMAGE_BASE64
        assert part.media_type == "image/png"
        assert part.data == "abc123"

    def test_from_dict_http_url(self):
        part = ContentPart.from_dict(
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/img.png"},
            }
        )
        assert part.type == ContentPartType.IMAGE_URL
        assert part.url == "https://example.com/img.png"

    def test_frozen(self):
        part = ContentPart(type=ContentPartType.TEXT, text="Hello")
        with pytest.raises(AttributeError):
            part.text = "World"  # type: ignore[misc]


# =============================================================================
# Typed-message converters (formats.py)
# =============================================================================


class TestMessagesToOpenAI:
    def test_basic_conversion(self):
        from clara_core.llm.tools.formats import messages_to_openai

        msgs: list[Message] = [
            SystemMessage(content="Be helpful"),
            UserMessage(content="Hi"),
            AssistantMessage(content="Hello!"),
        ]
        result = messages_to_openai(msgs)
        assert len(result) == 3
        assert result[0] == {"role": "system", "content": "Be helpful"}
        assert result[1] == {"role": "user", "content": "Hi"}
        assert result[2] == {"role": "assistant", "content": "Hello!"}

    def test_tool_result_conversion(self):
        from clara_core.llm.tools.formats import message_to_openai

        msg = ToolResultMessage(tool_call_id="call_1", content="42")
        result = message_to_openai(msg)
        assert result == {"role": "tool", "tool_call_id": "call_1", "content": "42"}


class TestMessagesToAnthropic:
    def test_extracts_system(self):
        from clara_core.llm.tools.formats import messages_to_anthropic

        msgs: list[Message] = [
            SystemMessage(content="Be helpful"),
            SystemMessage(content="Be concise"),
            UserMessage(content="Hi"),
        ]
        system, api_msgs = messages_to_anthropic(msgs)
        assert system == "Be helpful\n\nBe concise"
        assert len(api_msgs) == 1
        assert api_msgs[0] == {"role": "user", "content": "Hi"}

    def test_tool_result_becomes_user(self):
        from clara_core.llm.tools.formats import messages_to_anthropic

        msgs: list[Message] = [
            UserMessage(content="Hi"),
            ToolResultMessage(tool_call_id="call_1", content="42"),
        ]
        system, api_msgs = messages_to_anthropic(msgs)
        assert system == ""
        assert len(api_msgs) == 2
        assert api_msgs[1]["role"] == "user"
        assert api_msgs[1]["content"][0]["type"] == "tool_result"
        assert api_msgs[1]["content"][0]["tool_use_id"] == "call_1"

    def test_assistant_with_tool_calls(self):
        from clara_core.llm.tools.formats import message_to_anthropic

        tc = ToolCall(id="call_1", name="search", arguments={"q": "test"})
        msg = AssistantMessage(content="Searching", tool_calls=[tc])
        result = message_to_anthropic(msg)
        assert result["role"] == "assistant"
        assert isinstance(result["content"], list)
        assert result["content"][0] == {"type": "text", "text": "Searching"}
        assert result["content"][1]["type"] == "tool_use"
        assert result["content"][1]["name"] == "search"

    def test_multimodal_user_message(self):
        from clara_core.llm.tools.formats import message_to_anthropic

        parts = [
            ContentPart(type=ContentPartType.TEXT, text="Look"),
            ContentPart(
                type=ContentPartType.IMAGE_BASE64,
                media_type="image/png",
                data="abc123",
            ),
        ]
        msg = UserMessage(content="Look", parts=parts)
        result = message_to_anthropic(msg)
        assert result["role"] == "user"
        assert isinstance(result["content"], list)
        assert result["content"][0] == {"type": "text", "text": "Look"}
        assert result["content"][1]["type"] == "image"
        assert result["content"][1]["source"]["type"] == "base64"
        assert result["content"][1]["source"]["media_type"] == "image/png"
        assert result["content"][1]["source"]["data"] == "abc123"

    def test_image_url_user_message(self):
        from clara_core.llm.tools.formats import message_to_anthropic

        parts = [
            ContentPart(type=ContentPartType.IMAGE_URL, url="https://example.com/img.png"),
        ]
        msg = UserMessage(content="", parts=parts)
        result = message_to_anthropic(msg)
        assert result["content"][0]["type"] == "image"
        assert result["content"][0]["source"]["type"] == "url"
        assert result["content"][0]["source"]["url"] == "https://example.com/img.png"


class TestMessagesToLangchain:
    def test_basic_conversion(self):
        from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
        from langchain_core.messages import SystemMessage as LCSystemMessage

        from clara_core.llm.tools.formats import messages_to_langchain

        msgs: list[Message] = [
            SystemMessage(content="Be helpful"),
            UserMessage(content="Hi"),
            AssistantMessage(content="Hello!"),
            ToolResultMessage(tool_call_id="call_1", content="42"),
        ]
        lc_msgs = messages_to_langchain(msgs)

        assert len(lc_msgs) == 4
        assert isinstance(lc_msgs[0], LCSystemMessage)
        assert lc_msgs[0].content == "Be helpful"
        assert isinstance(lc_msgs[1], HumanMessage)
        assert lc_msgs[1].content == "Hi"
        assert isinstance(lc_msgs[2], AIMessage)
        assert lc_msgs[2].content == "Hello!"
        assert isinstance(lc_msgs[3], ToolMessage)
        assert lc_msgs[3].content == "42"
        assert lc_msgs[3].tool_call_id == "call_1"

    def test_assistant_with_tool_calls(self):
        from langchain_core.messages import AIMessage

        from clara_core.llm.tools.formats import messages_to_langchain

        tc = ToolCall(id="call_1", name="search", arguments={"q": "test"})
        msgs: list[Message] = [AssistantMessage(content="Searching", tool_calls=[tc])]
        lc_msgs = messages_to_langchain(msgs)

        assert len(lc_msgs) == 1
        ai_msg = lc_msgs[0]
        assert isinstance(ai_msg, AIMessage)
        assert ai_msg.content == "Searching"
        assert len(ai_msg.tool_calls) == 1
        assert ai_msg.tool_calls[0]["name"] == "search"
        assert ai_msg.tool_calls[0]["args"] == {"q": "test"}

    def test_multimodal_user(self):
        from langchain_core.messages import HumanMessage

        from clara_core.llm.tools.formats import messages_to_langchain

        parts = [
            ContentPart(type=ContentPartType.TEXT, text="Look"),
            ContentPart(
                type=ContentPartType.IMAGE_BASE64,
                media_type="image/png",
                data="abc",
            ),
        ]
        msgs: list[Message] = [UserMessage(content="Look", parts=parts)]
        lc_msgs = messages_to_langchain(msgs)

        assert len(lc_msgs) == 1
        assert isinstance(lc_msgs[0], HumanMessage)
        assert isinstance(lc_msgs[0].content, list)
        assert len(lc_msgs[0].content) == 2


# =============================================================================
# Bridge methods on ToolResponse / ToolCall
# =============================================================================


class TestToolResponseBridge:
    def test_to_assistant_message(self):
        tc = ToolCall(id="call_1", name="search", arguments={"q": "test"})
        response = ToolResponse(content="Searching", tool_calls=[tc])
        msg = response.to_assistant_message()

        assert isinstance(msg, AssistantMessage)
        assert msg.content == "Searching"
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0].name == "search"
        assert msg.tool_calls[0].id == "call_1"

    def test_to_assistant_message_no_tools(self):
        response = ToolResponse(content="Just text")
        msg = response.to_assistant_message()

        assert isinstance(msg, AssistantMessage)
        assert msg.content == "Just text"
        assert msg.tool_calls == []

    def test_to_assistant_message_none_content(self):
        tc = ToolCall(id="call_1", name="search", arguments={})
        response = ToolResponse(content=None, tool_calls=[tc])
        msg = response.to_assistant_message()

        assert msg.content is None
        assert len(msg.tool_calls) == 1


class TestToolCallBridge:
    def test_to_result_message(self):
        tc = ToolCall(id="call_1", name="search", arguments={"q": "test"})
        msg = tc.to_result_message("42")

        assert isinstance(msg, ToolResultMessage)
        assert msg.tool_call_id == "call_1"
        assert msg.content == "42"

    def test_to_result_message_empty_output(self):
        tc = ToolCall(id="call_2", name="noop", arguments={})
        msg = tc.to_result_message("")

        assert msg.tool_call_id == "call_2"
        assert msg.content == ""
