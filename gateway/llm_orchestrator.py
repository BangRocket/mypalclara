"""LLM orchestration for the Clara Gateway.

Handles:
- LLM calls with tool support
- Streaming response generation
- Multi-turn tool execution
- Multimodal image support
- Auto-continue for permission-seeking questions
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, AsyncIterator

from config.logging import get_logger
from gateway.protocol import AttachmentInfo, ResponseChunk, ToolResult, ToolStart

if TYPE_CHECKING:
    from websockets.server import WebSocketServerProtocol

logger = get_logger("gateway.llm")

# Dedicated thread pool for blocking LLM calls
LLM_EXECUTOR = ThreadPoolExecutor(
    max_workers=int(os.getenv("GATEWAY_LLM_THREADS", "10")),
    thread_name_prefix="gateway-llm-",
)

# Configuration
MAX_TOOL_ITERATIONS = int(os.getenv("GATEWAY_MAX_TOOL_ITERATIONS", "75"))
MAX_TOOL_RESULT_CHARS = int(os.getenv("GATEWAY_MAX_TOOL_RESULT_CHARS", "50000"))

# Tool calling mode: "xml" (OpenClaw-style system prompt injection) or "native" (API-based)
TOOL_CALL_MODE = os.getenv("TOOL_CALL_MODE", "xml").lower()

# Auto-continue configuration
AUTO_CONTINUE_ENABLED = os.getenv("AUTO_CONTINUE_ENABLED", "true").lower() == "true"
AUTO_CONTINUE_MAX = int(os.getenv("AUTO_CONTINUE_MAX", "3"))

# Permission-seeking patterns that trigger auto-continue
AUTO_CONTINUE_PATTERNS = [
    r"want me to .*\?",
    r"should i .*\?",
    r"shall i .*\?",
    r"would you like me to .*\?",
    r"ready to proceed\?",
    r"proceed\?",
    r"go ahead\?",
    r"continue\?",
    r"do you want me to .*\?",
    r"i can .* if you('d)? like",
    r"let me know if",
]


class LLMOrchestrator:
    """Orchestrates LLM calls with tool support.

    Handles the multi-turn loop of:
    1. Call LLM
    2. Detect tool calls
    3. Execute tools
    4. Add results to context
    5. Repeat until no more tools or max iterations
    """

    def __init__(self) -> None:
        """Initialize the orchestrator."""
        self._tool_executor: Any = None  # Will be set during initialization
        self._initialized = False

    async def initialize(self, tool_executor: Any) -> None:
        """Initialize with a tool executor.

        Args:
            tool_executor: ToolExecutor instance
        """
        self._tool_executor = tool_executor
        self._initialized = True
        logger.info("LLMOrchestrator initialized")

    async def generate_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        user_id: str,
        request_id: str,
        tier: str | None = None,
        websocket: WebSocketServerProtocol | None = None,
        images: list[AttachmentInfo] | None = None,
        auto_continue_count: int = 0,
    ) -> AsyncIterator[dict[str, Any]]:
        """Generate response with tool calling support.

        Yields events during processing:
        - tool_start: Tool execution started
        - tool_result: Tool execution completed
        - chunk: Response text chunk
        - complete: Final response

        Args:
            messages: Conversation messages
            tools: Available tool definitions
            user_id: User ID for tool context
            request_id: Request ID for tracking
            tier: Optional model tier (high/mid/low)
            websocket: WebSocket for sending updates
            images: Optional list of image attachments for vision
            auto_continue_count: Current auto-continue iteration (internal use)

        Yields:
            Event dicts with type and data
        """
        if not self._initialized:
            raise RuntimeError("LLMOrchestrator not initialized")

        loop = asyncio.get_event_loop()
        working_messages = list(messages)  # Copy to avoid mutation
        total_tools_run = 0
        files_to_send: list[str] = []

        # Add images to the last user message if present
        if images:
            working_messages = self._add_images_to_messages(working_messages, images)
            logger.info(f"[{request_id}] Added {len(images)} image(s) to context")

        # Add tool instruction
        tool_instruction = self._build_tool_instruction()
        working_messages.insert(0, tool_instruction)

        for iteration in range(MAX_TOOL_ITERATIONS):
            logger.debug(f"[{request_id}] Iteration {iteration + 1}/{MAX_TOOL_ITERATIONS}")

            # Call LLM
            response = await self._call_llm(
                working_messages,
                tools,
                tier,
                loop,
            )

            # Check for tool calls
            tool_calls = response.get("tool_calls")
            if not tool_calls:
                # No tools - return final response
                content = response.get("content") or ""
                messages_for_llm = [m for m in working_messages if m != tool_instruction]

                # Check if auto-continue might be needed
                might_auto_continue = (
                    AUTO_CONTINUE_ENABLED
                    and auto_continue_count < AUTO_CONTINUE_MAX
                )

                if iteration == 0 and not might_auto_continue:
                    # First iteration, no auto-continue - use real streaming
                    async for chunk in self._call_main_llm_streaming(
                        messages_for_llm,
                        tier,
                    ):
                        content += chunk
                        yield {"type": "chunk", "text": chunk}

                    yield {
                        "type": "complete",
                        "text": content,
                        "tool_count": total_tools_run,
                        "files": files_to_send,
                    }
                    return

                # Need non-streaming for auto-continue check or tool iterations
                if iteration == 0:
                    content = await self._call_main_llm(
                        messages_for_llm,
                        tier,
                        loop,
                        images=images,
                    )

                # Check for auto-continue (permission-seeking question)
                if might_auto_continue and self._should_auto_continue(content):
                    logger.info(
                        f"[{request_id}] Auto-continue triggered "
                        f"(iteration {auto_continue_count + 1}/{AUTO_CONTINUE_MAX})"
                    )

                    # Stream the response so far (simulated since we already have it)
                    async for chunk in self._stream_text(content):
                        yield {"type": "chunk", "text": chunk}

                    # Add assistant response and user confirmation
                    working_messages.append({"role": "assistant", "content": content})
                    working_messages.append({"role": "user", "content": "Yes, please proceed."})

                    # Recursive call for continuation
                    async for event in self.generate_with_tools(
                        messages=working_messages,
                        tools=tools,
                        user_id=user_id,
                        request_id=request_id,
                        tier=tier,
                        websocket=websocket,
                        images=None,  # Don't re-add images
                        auto_continue_count=auto_continue_count + 1,
                    ):
                        if event["type"] == "chunk":
                            yield event
                        elif event["type"] == "complete":
                            # Combine responses
                            yield {
                                "type": "complete",
                                "text": content + "\n\n" + event["text"],
                                "tool_count": total_tools_run + event.get("tool_count", 0),
                                "files": files_to_send + event.get("files", []),
                            }
                        else:
                            yield event
                    return

                # Stream the response (simulated since we already have content)
                async for chunk in self._stream_text(content):
                    yield {"type": "chunk", "text": chunk}

                yield {
                    "type": "complete",
                    "text": content,
                    "tool_count": total_tools_run,
                    "files": files_to_send,
                }
                return

            # Process tool calls
            working_messages.append(response)

            for tool_call in tool_calls:
                tool_name = tool_call["function"]["name"]
                try:
                    arguments = json.loads(tool_call["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    arguments = {}

                total_tools_run += 1

                # Emit tool start
                yield {
                    "type": "tool_start",
                    "tool_name": tool_name,
                    "step": total_tools_run,
                    "arguments": arguments,
                }

                # Execute tool
                output = await self._tool_executor.execute(
                    tool_name=tool_name,
                    arguments=arguments,
                    user_id=user_id,
                    files_to_send=files_to_send,
                )

                # Truncate if needed
                if len(output) > MAX_TOOL_RESULT_CHARS:
                    output = self._truncate_output(output)

                # Add to messages
                working_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": output,
                    }
                )

                # Emit tool result
                success = not output.startswith("Error:")
                yield {
                    "type": "tool_result",
                    "tool_name": tool_name,
                    "success": success,
                    "output_preview": output[:200] if len(output) > 200 else output,
                }

        # Max iterations reached
        logger.warning(f"[{request_id}] Max iterations reached")

        working_messages.append(
            {
                "role": "user",
                "content": "You've reached the maximum number of tool calls. Please summarize what you've accomplished.",
            }
        )

        final_response = await self._call_main_llm(working_messages, tier, loop)

        async for chunk in self._stream_text(final_response):
            yield {"type": "chunk", "text": chunk}

        yield {
            "type": "complete",
            "text": final_response,
            "tool_count": total_tools_run,
            "files": files_to_send,
        }

    async def _call_llm(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tier: str | None,
        loop: asyncio.AbstractEventLoop,
    ) -> dict[str, Any]:
        """Call LLM with tools.

        Supports two modes (controlled by TOOL_CALL_MODE env var):
        - "native": Uses API-native tool calling (OpenAI/Anthropic format)
        - "xml": OpenClaw-style system prompt injection

        Returns dict with content and optional tool_calls.
        """
        if TOOL_CALL_MODE == "xml":
            return await self._call_llm_xml(messages, tools, tier, loop)
        else:
            return await self._call_llm_native(messages, tools, tier, loop)

    async def _call_llm_native(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tier: str | None,
        loop: asyncio.AbstractEventLoop,
    ) -> dict[str, Any]:
        """Call LLM with native API tool calling.

        Returns dict with content and optional tool_calls.
        """
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
                    "content": msg.content,
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
                    else None,
                }

        return await loop.run_in_executor(LLM_EXECUTOR, call)

    async def _call_llm_xml(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tier: str | None,
        loop: asyncio.AbstractEventLoop,
    ) -> dict[str, Any]:
        """Call LLM with OpenClaw-style XML tool injection.

        Tools are serialized to XML and injected into the system prompt.
        Function calls are parsed from the response text.

        Returns dict with content and optional tool_calls.
        """
        from clara_core import ModelTier, make_llm_with_xml_tools

        model_tier = ModelTier(tier) if tier else None

        def call():
            llm = make_llm_with_xml_tools(tools, tier=model_tier)
            return llm(messages)

        return await loop.run_in_executor(LLM_EXECUTOR, call)

    async def _call_main_llm_streaming(
        self,
        messages: list[dict[str, Any]],
        tier: str | None,
    ) -> AsyncIterator[str]:
        """Call main LLM with streaming and yield chunks.

        Args:
            messages: Conversation messages
            tier: Optional model tier

        Yields:
            Response text chunks as they arrive
        """
        from clara_core import ModelTier, make_llm_streaming

        model_tier = ModelTier(tier) if tier else None
        loop = asyncio.get_event_loop()

        # Create the streaming LLM
        def get_stream():
            llm = make_llm_streaming(tier=model_tier)
            return llm(messages)

        # Get the stream generator in executor
        stream = await loop.run_in_executor(LLM_EXECUTOR, get_stream)

        # Yield chunks from the stream (each in executor to not block)
        def get_next_chunk(gen):
            try:
                return next(gen)
            except StopIteration:
                return None

        while True:
            chunk = await loop.run_in_executor(LLM_EXECUTOR, get_next_chunk, stream)
            if chunk is None:
                break
            yield chunk

    async def _call_main_llm(
        self,
        messages: list[dict[str, Any]],
        tier: str | None,
        loop: asyncio.AbstractEventLoop,
        images: list[AttachmentInfo] | None = None,
    ) -> str:
        """Call main LLM without tools (non-streaming fallback).

        Args:
            messages: Conversation messages
            tier: Optional model tier
            loop: Event loop for executor
            images: Optional images (already added to messages if present)

        Returns:
            Response text.
        """
        from clara_core import ModelTier, make_llm

        model_tier = ModelTier(tier) if tier else None

        def call():
            llm = make_llm(tier=model_tier)
            return llm(messages)

        return await loop.run_in_executor(LLM_EXECUTOR, call)

    async def _stream_text(self, text: str, chunk_size: int = 50) -> AsyncIterator[str]:
        """Simulate streaming by yielding text chunks.

        In future, this can be replaced with actual streaming from the LLM.
        """
        words = text.split()
        current_chunk: list[str] = []
        current_len = 0

        for word in words:
            current_chunk.append(word)
            current_len += len(word) + 1

            if current_len >= chunk_size:
                yield " ".join(current_chunk) + " "
                current_chunk = []
                current_len = 0
                await asyncio.sleep(0.01)  # Small delay for streaming effect

        if current_chunk:
            yield " ".join(current_chunk)

    def _build_tool_instruction(self) -> dict[str, str]:
        """Build the tool instruction system message."""
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

    def _truncate_output(self, output: str) -> str:
        """Truncate tool output if too long."""
        truncated = output[:MAX_TOOL_RESULT_CHARS]
        msg = (
            f"\n\n[TRUNCATED: Result was {len(output):,} chars, showing first {MAX_TOOL_RESULT_CHARS:,}. "
            f"Use pagination parameters (per_page, page) or more specific filters to get smaller results.]"
        )
        return truncated + msg

    def _add_images_to_messages(
        self,
        messages: list[dict[str, Any]],
        images: list[AttachmentInfo],
    ) -> list[dict[str, Any]]:
        """Add images to the last user message for vision processing.

        Converts images to the appropriate format based on LLM provider.

        Args:
            messages: Conversation messages
            images: List of image attachments

        Returns:
            Updated messages with images embedded
        """
        if not images:
            return messages

        provider = os.getenv("LLM_PROVIDER", "openrouter").lower()

        # Find the last user message
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "user":
                user_msg = messages[i]

                # Build multimodal content
                content_parts = []

                # Add existing text content
                existing_content = user_msg.get("content", "")
                if isinstance(existing_content, str):
                    content_parts.append({"type": "text", "text": existing_content})
                elif isinstance(existing_content, list):
                    content_parts.extend(existing_content)

                # Add images
                for img in images:
                    if img.type != "image" or not img.base64_data:
                        continue

                    if provider == "anthropic":
                        # Anthropic native format
                        content_parts.append(
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": img.media_type or "image/jpeg",
                                    "data": img.base64_data,
                                },
                            }
                        )
                    else:
                        # OpenAI/OpenRouter format
                        content_parts.append(
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{img.media_type or 'image/jpeg'};base64,{img.base64_data}",
                                },
                            }
                        )

                # Update message with multimodal content
                messages[i] = {
                    **user_msg,
                    "content": content_parts,
                }
                break

        return messages

    def _should_auto_continue(self, response: str) -> bool:
        """Check if response ends with a permission-seeking question.

        Args:
            response: The LLM response text

        Returns:
            True if auto-continue should be triggered
        """
        if not response:
            return False

        # Get the last ~200 chars to check for patterns
        tail = response[-200:].lower().strip()

        for pattern in AUTO_CONTINUE_PATTERNS:
            if re.search(pattern, tail, re.IGNORECASE):
                return True

        return False
