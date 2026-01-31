"""LLM orchestration for the Clara Gateway.

Handles:
- LLM calls with tool support
- Streaming response generation
- Multi-turn tool execution
"""

from __future__ import annotations

import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, AsyncIterator

from config.logging import get_logger
from gateway.protocol import ResponseChunk, ToolResult, ToolStart

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

        Yields:
            Event dicts with type and data
        """
        if not self._initialized:
            raise RuntimeError("LLMOrchestrator not initialized")

        loop = asyncio.get_event_loop()
        working_messages = list(messages)  # Copy to avoid mutation
        total_tools_run = 0
        files_to_send: list[str] = []

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
                if iteration == 0:
                    # First iteration with no tools - use main LLM
                    content = await self._call_main_llm(
                        [m for m in working_messages if m != tool_instruction],
                        tier,
                        loop,
                    )

                # Stream the response
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

    async def _call_main_llm(
        self,
        messages: list[dict[str, Any]],
        tier: str | None,
        loop: asyncio.AbstractEventLoop,
    ) -> str:
        """Call main LLM without tools.

        Returns response text.
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
