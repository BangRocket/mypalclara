"""Cognition Reflector - Fire-and-forget memory storage.

This module implements the REFLECT stage of the cognition pipeline:
- Store exchange to memory (one-way, no feedback)
- Update session state
- Optional pattern tracking for future improvements

CRITICAL: Reflection is fire-and-forget. It does NOT return any value
and does NOT feed back into the pipeline. It stores asynchronously
using asyncio.create_task to avoid blocking the response.

This design enables:
- Immediate response delivery to user
- Background memory extraction
- No latency impact on response
"""

from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from clara_core.cognition.types import (
    CognitionEvent,
    ContextBundle,
    ResponseCompleteEvent,
)

if TYPE_CHECKING:
    from clara_core.memory import MemoryManager

logger = logging.getLogger(__name__)

# Thread pool for blocking memory operations
REFLECT_EXECUTOR = ThreadPoolExecutor(
    max_workers=int(os.getenv("REFLECT_IO_THREADS", "5")),
    thread_name_prefix="reflect-io-",
)


@dataclass
class ReflectorConfig:
    """Configuration for the Reflector."""

    # Memory storage settings
    store_to_memory: bool = True  # Whether to store exchanges to mem0
    update_session: bool = True  # Whether to update session state

    # Pattern tracking settings
    track_patterns: bool = True  # Whether to track interaction patterns
    pattern_window_size: int = 10  # Number of interactions to consider


@dataclass
class ReflectionMetadata:
    """Metadata about a reflection operation."""

    user_id: str = ""
    channel_id: str = ""
    session_id: str = ""
    user_message: str = ""
    assistant_reply: str = ""
    is_dm: bool = False
    participants: list[dict[str, Any]] = field(default_factory=list)
    project_id: str = ""


class Reflector:
    """Fire-and-forget memory storage after response generation.

    The Reflector:
    1. Stores the exchange to mem0 via MemoryManager
    2. Updates session state
    3. Optionally tracks patterns (write-only)

    IMPORTANT: All operations are fire-and-forget. The reflect() method
    schedules work asynchronously and returns immediately. Errors are
    logged but do not propagate.

    Attributes:
        config: Reflector configuration
        _memory_manager: Optional MemoryManager instance
    """

    def __init__(
        self,
        config: ReflectorConfig | None = None,
        memory_manager: "MemoryManager | None" = None,
    ) -> None:
        """Initialize the reflector.

        Args:
            config: Optional configuration, uses defaults if not provided
            memory_manager: Optional MemoryManager instance. If not provided,
                           attempts to get singleton instance.
        """
        self.config = config or ReflectorConfig()
        self._memory_manager = memory_manager

    def _get_memory_manager(self) -> "MemoryManager":
        """Get the MemoryManager instance.

        Returns:
            MemoryManager singleton or provided instance

        Raises:
            RuntimeError: If no MemoryManager is available
        """
        if self._memory_manager is not None:
            return self._memory_manager

        from clara_core.memory import MemoryManager

        return MemoryManager.get_instance()

    async def reflect(
        self,
        event: CognitionEvent,
        context: ContextBundle,
        response: ResponseCompleteEvent,
    ) -> None:
        """Store exchange to memory (fire-and-forget).

        This method schedules reflection asynchronously and returns immediately.
        The actual work happens in background tasks.

        IMPORTANT: This method has no return value. It does NOT feed back
        into the pipeline.

        Args:
            event: The original cognition event
            context: The context bundle used for generation
            response: The completed response
        """
        if not self.config.store_to_memory:
            logger.debug("Memory storage disabled, skipping reflection")
            return

        # Build reflection metadata
        metadata = ReflectionMetadata(
            user_id=event.metadata.user_id,
            channel_id=event.metadata.channel_id,
            session_id=context.session_id,
            user_message=event.content,
            assistant_reply=response.full_text,
            is_dm=context.channel_type == "dm",
            participants=event.payload.get("participants", []),
            project_id=event.payload.get("project_id", ""),
        )

        # Schedule fire-and-forget tasks
        asyncio.create_task(
            self._store_to_memory(metadata, context),
            name=f"reflect-memory-{event.request_id}",
        )

        if self.config.track_patterns:
            asyncio.create_task(
                self._note_patterns(metadata, response),
                name=f"reflect-patterns-{event.request_id}",
            )

    async def _store_to_memory(
        self,
        metadata: ReflectionMetadata,
        context: ContextBundle,
    ) -> None:
        """Store the exchange to mem0.

        Args:
            metadata: Reflection metadata
            context: Context bundle with session messages
        """
        try:
            loop = asyncio.get_event_loop()
            mm = self._get_memory_manager()

            # Convert session messages to message-like objects
            recent_msgs = self._convert_to_messages(context.session_messages)

            def _store():
                mm.add_to_mem0(
                    user_id=metadata.user_id,
                    project_id=metadata.project_id,
                    recent_msgs=recent_msgs,
                    user_message=metadata.user_message,
                    assistant_reply=metadata.assistant_reply,
                    participants=metadata.participants,
                    is_dm=metadata.is_dm,
                )

            await loop.run_in_executor(REFLECT_EXECUTOR, _store)

            logger.debug(
                "Stored exchange to memory for user %s, session %s",
                metadata.user_id,
                metadata.session_id,
            )

        except Exception as e:
            # Log but don't propagate - fire-and-forget
            logger.error(
                "Failed to store exchange to memory: %s (user=%s, session=%s)",
                e,
                metadata.user_id,
                metadata.session_id,
            )

    async def _note_patterns(
        self,
        metadata: ReflectionMetadata,
        response: ResponseCompleteEvent,
    ) -> None:
        """Track interaction patterns (write-only).

        This is a placeholder for future pattern analysis. Currently logs
        basic metrics but does not affect pipeline behavior.

        Args:
            metadata: Reflection metadata
            response: The completed response
        """
        try:
            # Note: This is write-only pattern tracking
            # These patterns could be used for:
            # - Model tier prediction
            # - Response strategy optimization
            # - User preference learning

            patterns = {
                "user_id": metadata.user_id,
                "session_id": metadata.session_id,
                "is_dm": metadata.is_dm,
                "message_length": len(metadata.user_message),
                "response_length": len(metadata.assistant_reply),
                "tool_count": response.tool_count,
                "has_tools": response.tool_count > 0,
            }

            logger.debug(
                "Noted patterns: user=%s, tools=%d, msg_len=%d, resp_len=%d",
                metadata.user_id,
                response.tool_count,
                len(metadata.user_message),
                len(metadata.assistant_reply),
            )

            # Future: Store patterns for analysis
            # For now, just log for observability

        except Exception as e:
            # Log but don't propagate - fire-and-forget
            logger.debug("Pattern tracking failed (non-critical): %s", e)

    def _convert_to_messages(
        self,
        session_messages: list[dict[str, Any]],
    ) -> list[Any]:
        """Convert session message dicts to Message-like objects.

        The MemoryManager.add_to_mem0 expects objects with .role, .content
        attributes. This creates simple wrapper objects.

        Args:
            session_messages: List of message dicts with role/content

        Returns:
            List of message-like objects
        """

        class MessageWrapper:
            """Simple wrapper to satisfy Message interface."""

            def __init__(self, role: str, content: str):
                self.role = role
                self.content = content
                self.created_at = None

        return [
            MessageWrapper(m.get("role", "user"), m.get("content", ""))
            for m in session_messages
        ]


def create_reflector(
    memory_manager: "MemoryManager | None" = None,
    store_to_memory: bool = True,
    track_patterns: bool = True,
) -> Reflector:
    """Factory function to create a configured Reflector.

    Args:
        memory_manager: Optional MemoryManager instance
        store_to_memory: Whether to store exchanges to mem0
        track_patterns: Whether to track interaction patterns

    Returns:
        Configured Reflector instance
    """
    config = ReflectorConfig(
        store_to_memory=store_to_memory,
        track_patterns=track_patterns,
    )
    return Reflector(config=config, memory_manager=memory_manager)
