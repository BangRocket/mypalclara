"""LLM orchestration for the Clara Gateway.

DEPRECATED: The internal tool loop has been moved to the cognition pipeline.
This module is retained for direct LLM calls without pipeline processing.

For new code, use the cognition pipeline via MessageProcessor:
    from gateway.processor import MessageProcessor

This module now provides:
- Direct LLM calls (no tool loop)
- Utility functions for LLM interaction

The full tool calling loop with rate limiting is now handled by:
- clara_core.cognition.pipeline.CognitionPipeline
- gateway.processor.MessageProcessor (for gateway integration)
"""

from __future__ import annotations

import asyncio
import os
import warnings
from concurrent.futures import ThreadPoolExecutor
from typing import Any, AsyncIterator

from config.logging import get_logger

logger = get_logger("gateway.llm")

# Dedicated thread pool for blocking LLM calls
LLM_EXECUTOR = ThreadPoolExecutor(
    max_workers=int(os.getenv("GATEWAY_LLM_THREADS", "10")),
    thread_name_prefix="gateway-llm-",
)

# Configuration
MAX_TOOL_RESULT_CHARS = int(os.getenv("GATEWAY_MAX_TOOL_RESULT_CHARS", "50000"))


class LLMOrchestrator:
    """Direct LLM interaction without tool loop.

    DEPRECATED: For message processing with tools, use CognitionPipeline.

    This class is retained for cases where direct LLM calls are needed
    without the full cognition pipeline (e.g., classification, summarization).

    The tool calling loop has been moved to:
    - CognitionPipeline.process() for rate-limited tool execution
    - MessageProcessor._process_with_tools() for gateway integration

    Usage for direct LLM calls:
        orchestrator = LLMOrchestrator()
        await orchestrator.initialize()

        # Simple call without tools
        response = await orchestrator.call_llm(messages, tier="mid")

        # Stream a response
        async for chunk in orchestrator.stream_text(text):
            print(chunk, end="")
    """

    def __init__(self) -> None:
        """Initialize the orchestrator."""
        self._initialized = False
        warnings.warn(
            "LLMOrchestrator is deprecated for tool calling. "
            "Use CognitionPipeline for message processing with tools.",
            DeprecationWarning,
            stacklevel=2,
        )

    async def initialize(self, tool_executor: Any = None) -> None:
        """Initialize the orchestrator.

        Args:
            tool_executor: Ignored (retained for compatibility).
                          Tool execution is now handled by MessageProcessor.
        """
        if tool_executor is not None:
            logger.warning(
                "LLMOrchestrator.initialize(): tool_executor parameter is ignored. "
                "Tool execution is now handled by CognitionPipeline."
            )
        self._initialized = True
        logger.info("LLMOrchestrator initialized (deprecated - use CognitionPipeline)")

    async def call_llm(
        self,
        messages: list[dict[str, Any]],
        tier: str | None = None,
    ) -> str:
        """Call LLM without tools.

        This is a direct LLM call for simple use cases like classification
        or summarization that don't need the full cognition pipeline.

        Args:
            messages: Conversation messages
            tier: Optional model tier (high/mid/low)

        Returns:
            Response text
        """
        if not self._initialized:
            raise RuntimeError("LLMOrchestrator not initialized")

        loop = asyncio.get_event_loop()
        return await self._call_main_llm(messages, tier, loop)

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

    async def stream_text(
        self, text: str, chunk_size: int = 50
    ) -> AsyncIterator[str]:
        """Simulate streaming by yielding text chunks.

        Useful for presenting pre-generated text with a streaming effect.

        Args:
            text: Text to stream
            chunk_size: Approximate characters per chunk

        Yields:
            Text chunks
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

    def truncate_output(self, output: str) -> str:
        """Truncate tool output if too long.

        Args:
            output: Output to truncate

        Returns:
            Truncated output with message
        """
        if len(output) <= MAX_TOOL_RESULT_CHARS:
            return output

        truncated = output[:MAX_TOOL_RESULT_CHARS]
        msg = (
            f"\n\n[TRUNCATED: Result was {len(output):,} chars, "
            f"showing first {MAX_TOOL_RESULT_CHARS:,}. "
            f"Use pagination parameters (per_page, page) or more specific "
            f"filters to get smaller results.]"
        )
        return truncated + msg
