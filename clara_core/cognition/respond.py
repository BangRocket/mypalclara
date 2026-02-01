"""Cognition Responder - LLM response generation with tool event emission.

This module implements the RESPOND stage of the cognition pipeline:
- LLM response generation with streaming
- Model tier selection from EvaluationResult
- Tool call detection and event emission
- Text chunk streaming

CRITICAL: The Responder does NOT execute tools internally. It detects tool
calls in the LLM response and yields ToolCallEvent objects. The pipeline
orchestrator handles tool execution, rate limiting, and re-entry.

This design enables:
- Rate limiting at the pipeline level (10 per-request, 20 per-minute)
- Tool execution policies (skip, mock, defer)
- Clean separation between detection and execution
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, AsyncIterator

from clara_core.cognition.types import (
    ContextBundle,
    EvaluationResult,
    ResponseCompleteEvent,
    TextChunkEvent,
    ToolCallEvent,
)

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

# Thread pool for blocking LLM calls
LLM_EXECUTOR = ThreadPoolExecutor(
    max_workers=int(os.getenv("RESPOND_LLM_THREADS", "10")),
    thread_name_prefix="respond-llm-",
)


@dataclass
class ResponderConfig:
    """Configuration for the Responder."""

    # Model settings
    default_tier: str = "mid"  # Default model tier if not specified
    use_streaming: bool = True  # Whether to stream responses

    # Tool instruction
    include_tool_instruction: bool = True

    # Chunk settings for simulated streaming
    chunk_size: int = 50  # Characters per chunk for simulated streaming
    chunk_delay: float = 0.01  # Delay between chunks (seconds)


class Responder:
    """Generates LLM responses with tool call detection.

    The Responder:
    1. Calls the LLM with assembled context
    2. Yields TextChunkEvent for streaming text
    3. Yields ToolCallEvent for each detected tool call
    4. Yields ResponseCompleteEvent when done

    Tool calls are NOT executed - they are emitted as events for the
    pipeline to handle.

    Attributes:
        config: Responder configuration
        _llm_fn: Function to call LLM (sync or async)
        _llm_with_tools_fn: Function to call LLM with tools
    """

    def __init__(
        self,
        config: ResponderConfig | None = None,
        llm_fn: Callable | None = None,
        llm_with_tools_fn: Callable | None = None,
    ) -> None:
        """Initialize the responder.

        Args:
            config: Optional configuration, uses defaults if not provided
            llm_fn: Optional function for LLM calls without tools
            llm_with_tools_fn: Optional function for LLM calls with tools
        """
        self.config = config or ResponderConfig()
        self._llm_fn = llm_fn
        self._llm_with_tools_fn = llm_with_tools_fn

    async def generate(
        self,
        context: ContextBundle,
        tools: list[dict[str, Any]] | None = None,
        evaluation: EvaluationResult | None = None,
        request_id: str = "",
    ) -> AsyncIterator[TextChunkEvent | ToolCallEvent | ResponseCompleteEvent]:
        """Generate LLM response, yielding events.

        This is an async generator that yields:
        - TextChunkEvent: For each chunk of streamed text
        - ToolCallEvent: For each tool call detected
        - ResponseCompleteEvent: When generation is complete

        Args:
            context: The assembled ContextBundle
            tools: Optional list of tool definitions
            evaluation: Optional evaluation result for tier selection
            request_id: Request ID for tracking

        Yields:
            Stream events (text chunks, tool calls, completion)
        """
        loop = asyncio.get_event_loop()

        # Determine model tier
        tier = self._get_tier(evaluation)

        # Prepare messages
        messages = list(context.messages)

        # Add tool instruction if needed
        if tools and self.config.include_tool_instruction:
            tool_instruction = self._build_tool_instruction()
            messages.insert(0, tool_instruction)

        # Call LLM
        if tools:
            response = await self._call_llm_with_tools(
                loop, messages, tools, tier
            )
        else:
            response = await self._call_llm(loop, messages, tier)

        # Process response
        tool_calls = response.get("tool_calls", [])
        content = response.get("content", "")
        tool_count = 0

        # If there are tool calls, emit them as events
        if tool_calls:
            for tc in tool_calls:
                tool_count += 1
                tool_event = self._parse_tool_call(tc, request_id)
                yield tool_event

            # Yield any text content as a single chunk
            if content:
                yield TextChunkEvent(
                    text=content,
                    is_final=True,
                    request_id=request_id,
                )
        else:
            # Stream text response
            async for chunk in self._stream_text(content, request_id):
                yield chunk

        # Yield completion event
        yield ResponseCompleteEvent(
            full_text=content,
            tool_count=tool_count,
            request_id=request_id,
            metadata={
                "tier": tier,
                "has_tool_calls": len(tool_calls) > 0,
            },
        )

    def _get_tier(self, evaluation: EvaluationResult | None) -> str:
        """Get model tier from evaluation or default.

        Args:
            evaluation: Optional evaluation result

        Returns:
            Model tier string ("low", "mid", "high")
        """
        if evaluation and evaluation.suggested_tier:
            return evaluation.suggested_tier
        return self.config.default_tier

    async def _call_llm(
        self,
        loop: asyncio.AbstractEventLoop,
        messages: list[dict[str, Any]],
        tier: str,
    ) -> dict[str, Any]:
        """Call LLM without tools.

        Args:
            loop: Event loop for executor
            messages: Conversation messages
            tier: Model tier

        Returns:
            Response dict with content
        """
        if self._llm_fn is None:
            from clara_core import ModelTier, make_llm

            def call():
                model_tier = ModelTier(tier) if tier else None
                llm = make_llm(tier=model_tier)
                return llm(messages)

            content = await loop.run_in_executor(LLM_EXECUTOR, call)
            return {"content": content, "tool_calls": []}

        # Use provided LLM function
        if asyncio.iscoroutinefunction(self._llm_fn):
            content = await self._llm_fn(messages, tier)
        else:
            content = await loop.run_in_executor(
                LLM_EXECUTOR, lambda: self._llm_fn(messages, tier)
            )

        return {"content": content, "tool_calls": []}

    async def _call_llm_with_tools(
        self,
        loop: asyncio.AbstractEventLoop,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tier: str,
    ) -> dict[str, Any]:
        """Call LLM with tools.

        Args:
            loop: Event loop for executor
            messages: Conversation messages
            tools: Tool definitions
            tier: Model tier

        Returns:
            Response dict with content and optional tool_calls
        """
        if self._llm_with_tools_fn is None:
            from clara_core import (
                ModelTier,
                anthropic_to_openai_response,
                make_llm_with_tools,
                make_llm_with_tools_anthropic,
            )

            provider = os.getenv("LLM_PROVIDER", "openrouter").lower()
            model_tier = ModelTier(tier) if tier else None

            def call():
                if provider == "anthropic":
                    llm = make_llm_with_tools_anthropic(tools, tier=model_tier)
                    response = llm(messages)
                    return anthropic_to_openai_response(response)
                else:
                    llm = make_llm_with_tools(tools, tier=model_tier)
                    completion = llm(messages)
                    msg = completion.choices[0].message
                    return {
                        "content": msg.content or "",
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in (msg.tool_calls or [])
                        ]
                        if msg.tool_calls
                        else [],
                    }

            return await loop.run_in_executor(LLM_EXECUTOR, call)

        # Use provided LLM function
        if asyncio.iscoroutinefunction(self._llm_with_tools_fn):
            return await self._llm_with_tools_fn(messages, tools, tier)
        else:
            return await loop.run_in_executor(
                LLM_EXECUTOR,
                lambda: self._llm_with_tools_fn(messages, tools, tier),
            )

    def _parse_tool_call(
        self,
        tool_call: dict[str, Any],
        request_id: str,
    ) -> ToolCallEvent:
        """Parse a tool call dict into a ToolCallEvent.

        Args:
            tool_call: Tool call dict from LLM response
            request_id: Request ID for tracking

        Returns:
            ToolCallEvent with parsed data
        """
        function_data = tool_call.get("function", {})
        tool_name = function_data.get("name", "")

        # Parse arguments - handle both string and dict
        arguments = function_data.get("arguments", "{}")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                logger.warning(
                    "Failed to parse tool arguments for %s: %s",
                    tool_name,
                    arguments[:100],
                )
                arguments = {}

        return ToolCallEvent(
            tool_name=tool_name,
            tool_args=arguments,
            call_id=tool_call.get("id", f"call-{uuid.uuid4().hex[:8]}"),
            request_id=request_id,
        )

    async def _stream_text(
        self,
        text: str,
        request_id: str,
    ) -> AsyncIterator[TextChunkEvent]:
        """Stream text in chunks.

        Simulates streaming by yielding chunks with delays.
        In future, this can be replaced with actual streaming.

        Args:
            text: Full text to stream
            request_id: Request ID for tracking

        Yields:
            TextChunkEvent for each chunk
        """
        if not text:
            return

        words = text.split()
        current_chunk: list[str] = []
        current_len = 0
        accumulated = ""

        for i, word in enumerate(words):
            current_chunk.append(word)
            current_len += len(word) + 1

            if current_len >= self.config.chunk_size or i == len(words) - 1:
                chunk_text = " ".join(current_chunk)
                if i < len(words) - 1:
                    chunk_text += " "

                accumulated += chunk_text
                is_final = i == len(words) - 1

                yield TextChunkEvent(
                    text=chunk_text,
                    is_final=is_final,
                    request_id=request_id,
                )

                current_chunk = []
                current_len = 0

                if not is_final:
                    await asyncio.sleep(self.config.chunk_delay)

    def _build_tool_instruction(self) -> dict[str, str]:
        """Build the tool instruction system message.

        Returns:
            System message dict with tool usage instructions
        """
        return {
            "role": "system",
            "content": (
                "CRITICAL FILE ATTACHMENT RULES:\n"
                "To share files (HTML, JSON, code, etc.) use `create_file_attachment` tool.\n"
                "This is the MOST RELIABLE method - it saves AND attaches in one step.\n"
                "NEVER paste raw HTML, large JSON, or long code directly into chat.\n\n"
                "You have access to tools for code execution, file management, and developer integrations. "
                "When the user asks you to calculate, run code, analyze data, "
                "fetch URLs, install packages, or do anything computational - "
                "USE THE TOOLS. Do not just explain what you would do - actually "
                "call the execute_python or other tools to do it. "
                "For any math beyond basic arithmetic, USE execute_python. "
                "For GitHub tasks (repos, issues, PRs, workflows), use the github_* tools. "
                "Summarize results conversationally and attach full output as a file."
            ),
        }


def create_responder(
    default_tier: str = "mid",
    use_streaming: bool = True,
) -> Responder:
    """Factory function to create a configured Responder.

    Args:
        default_tier: Default model tier if not specified
        use_streaming: Whether to stream responses

    Returns:
        Configured Responder instance
    """
    config = ResponderConfig(
        default_tier=default_tier,
        use_streaming=use_streaming,
    )
    return Responder(config=config)
