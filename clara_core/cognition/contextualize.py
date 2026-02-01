"""Cognition Contextualizer - Memory and session context assembly.

This module implements the CONTEXTUALIZE stage of the cognition pipeline:
- Session retrieval/creation
- Memory fetching from mem0
- Emotional context loading
- Context bundle assembly for LLM generation

The contextualizer transforms a CognitionEvent into a fully-populated
ContextBundle containing all context needed for response generation.
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
    EvaluationResult,
)

if TYPE_CHECKING:
    from clara_core.memory import MemoryManager

logger = logging.getLogger(__name__)

# Thread pool for blocking memory operations
CONTEXT_EXECUTOR = ThreadPoolExecutor(
    max_workers=int(os.getenv("CONTEXT_IO_THREADS", "10")),
    thread_name_prefix="context-io-",
)


@dataclass
class ContextualizerConfig:
    """Configuration for the Contextualizer."""

    # Session settings
    session_idle_minutes: int = 30
    max_session_messages: int = 20

    # Memory settings
    fetch_user_memories: bool = True
    fetch_project_memories: bool = True
    fetch_emotional_context: bool = True
    max_memories: int = 50
    max_emotional_contexts: int = 3

    # Graph memory settings
    fetch_graph_relations: bool = True
    max_graph_relations: int = 20


@dataclass
class SessionInfo:
    """Information about the current session."""

    session_id: str = ""
    user_id: str = ""
    context_id: str = ""
    project_id: str | None = None
    is_new_session: bool = False
    message_count: int = 0
    session_summary: str | None = None
    recent_messages: list[dict[str, Any]] = field(default_factory=list)


class Contextualizer:
    """Assembles full context for LLM generation.

    The Contextualizer performs sequential context fetching:
    1. Session retrieval/creation (from database)
    2. Memory fetching (from mem0)
    3. Emotional context loading (for tone calibration)
    4. ContextBundle assembly

    All blocking operations are run in a thread pool to avoid blocking
    the async event loop.

    Attributes:
        config: Contextualizer configuration
        _memory_manager: Optional MemoryManager instance
    """

    def __init__(
        self,
        config: ContextualizerConfig | None = None,
        memory_manager: "MemoryManager | None" = None,
    ) -> None:
        """Initialize the contextualizer.

        Args:
            config: Optional configuration, uses defaults if not provided
            memory_manager: Optional MemoryManager instance. If not provided,
                           attempts to get singleton instance.
        """
        self.config = config or ContextualizerConfig()
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

    async def contextualize(
        self,
        event: CognitionEvent,
        evaluation: EvaluationResult | None = None,
    ) -> ContextBundle:
        """Build complete context for LLM generation.

        Performs sequential context fetching:
        1. Get/create session
        2. Fetch memories from mem0
        3. Load emotional context
        4. Build LLM message list

        Args:
            event: The cognition event to build context for
            evaluation: Optional evaluation result for additional hints

        Returns:
            Complete ContextBundle ready for LLM generation
        """
        loop = asyncio.get_event_loop()
        mm = self._get_memory_manager()

        # Extract identifiers
        user_id = event.metadata.user_id
        channel_id = event.metadata.channel_id
        content = event.content
        is_dm = event.payload.get("is_dm", False)

        # 1. Get or create session
        session_info = await self._get_session(
            loop, mm, user_id, channel_id, is_dm
        )

        # 2. Fetch memories from mem0
        user_mems, proj_mems, graph_relations = await self._fetch_memories(
            loop, mm, user_id, session_info.project_id, content, is_dm
        )

        # 3. Get emotional context (for tone calibration)
        emotional_state = await self._get_emotional_state(
            loop, mm, user_id
        )

        # 4. Build the LLM message list
        messages = await loop.run_in_executor(
            CONTEXT_EXECUTOR,
            lambda: mm.build_prompt(
                user_mems=user_mems,
                proj_mems=proj_mems,
                thread_summary=session_info.session_summary,
                recent_msgs=self._convert_to_messages(session_info.recent_messages),
                user_message=content,
                graph_relations=graph_relations,
            ),
        )

        # 5. Assemble the ContextBundle
        bundle = ContextBundle(
            # Memory context
            memories=user_mems,
            project_memories=proj_mems,
            # Session context
            session_id=session_info.session_id,
            session_messages=session_info.recent_messages,
            # User context
            user_id=user_id,
            user_name=event.payload.get("user_name", ""),
            emotional_state=emotional_state,
            # Channel context
            channel_id=channel_id,
            channel_type="dm" if is_dm else event.payload.get("channel_type", "server"),
            # Assembled messages
            messages=messages,
        )

        logger.debug(
            "Contextualized event %s: %d memories, %d project mems, %d session msgs",
            event.request_id,
            len(user_mems),
            len(proj_mems),
            len(session_info.recent_messages),
        )

        return bundle

    async def _get_session(
        self,
        loop: asyncio.AbstractEventLoop,
        mm: "MemoryManager",
        user_id: str,
        channel_id: str,
        is_dm: bool,
    ) -> SessionInfo:
        """Get or create a session for the user/channel.

        Args:
            loop: Event loop for executor
            mm: MemoryManager instance
            user_id: User identifier
            channel_id: Channel identifier
            is_dm: Whether this is a direct message

        Returns:
            SessionInfo with session details
        """
        from db import get_db

        # Build context_id for session isolation
        if is_dm:
            context_id = f"dm-{user_id}"
        else:
            context_id = f"channel-{channel_id}"

        def _get_or_create():
            with get_db() as db:
                session = mm.get_or_create_session(
                    db=db,
                    user_id=user_id,
                    context_id=context_id,
                )

                # Get recent messages
                recent = mm.get_recent_messages(db, session.id)
                msg_count = mm.get_message_count(db, session.id)

                return SessionInfo(
                    session_id=str(session.id),
                    user_id=user_id,
                    context_id=context_id,
                    project_id=str(session.project_id) if session.project_id else None,
                    is_new_session=(msg_count == 0),
                    message_count=msg_count,
                    session_summary=session.session_summary,
                    recent_messages=[
                        {"role": m.role, "content": m.content}
                        for m in recent
                    ],
                )

        try:
            return await loop.run_in_executor(CONTEXT_EXECUTOR, _get_or_create)
        except Exception as e:
            logger.error("Failed to get session: %s", e)
            # Return minimal session info on error
            return SessionInfo(
                user_id=user_id,
                context_id=context_id,
            )

    async def _fetch_memories(
        self,
        loop: asyncio.AbstractEventLoop,
        mm: "MemoryManager",
        user_id: str,
        project_id: str | None,
        query: str,
        is_dm: bool,
    ) -> tuple[list[str], list[str], list[dict[str, Any]]]:
        """Fetch relevant memories from mem0.

        Args:
            loop: Event loop for executor
            mm: MemoryManager instance
            user_id: User identifier
            project_id: Optional project identifier
            query: Search query (usually user message)
            is_dm: Whether this is a direct message

        Returns:
            Tuple of (user_memories, project_memories, graph_relations)
        """
        if not self.config.fetch_user_memories:
            return [], [], []

        def _fetch():
            return mm.fetch_mem0_context(
                user_id=user_id,
                project_id=project_id or "",
                user_message=query,
                participants=[],
                is_dm=is_dm,
            )

        try:
            return await loop.run_in_executor(CONTEXT_EXECUTOR, _fetch)
        except Exception as e:
            logger.error("Failed to fetch memories: %s", e)
            return [], [], []

    async def _get_emotional_state(
        self,
        loop: asyncio.AbstractEventLoop,
        mm: "MemoryManager",
        user_id: str,
    ) -> str:
        """Get emotional state from recent session context.

        Args:
            loop: Event loop for executor
            mm: MemoryManager instance
            user_id: User identifier

        Returns:
            Emotional state string (e.g., "neutral", "stressed", "happy")
        """
        if not self.config.fetch_emotional_context:
            return "neutral"

        def _fetch_emotional():
            contexts = mm.fetch_emotional_context(
                user_id=user_id,
                limit=self.config.max_emotional_contexts,
            )
            if not contexts:
                return "neutral"

            # Extract most recent emotional state
            latest = contexts[0]
            arc = latest.get("arc", "stable")
            energy = latest.get("energy", "neutral")

            # Map to emotional state string
            if arc == "declining" or energy == "stressed":
                return "stressed"
            elif arc == "improving" or energy in ("excited", "happy"):
                return "positive"
            elif energy == "casual":
                return "casual"
            return "neutral"

        try:
            return await loop.run_in_executor(CONTEXT_EXECUTOR, _fetch_emotional)
        except Exception as e:
            logger.error("Failed to fetch emotional context: %s", e)
            return "neutral"

    def _convert_to_messages(
        self,
        session_messages: list[dict[str, Any]],
    ) -> list[Any]:
        """Convert session message dicts to Message-like objects.

        The MemoryManager.build_prompt expects objects with .role, .content,
        and optionally .created_at attributes. This creates simple wrapper
        objects to satisfy that interface.

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


def create_contextualizer(
    memory_manager: "MemoryManager | None" = None,
    fetch_emotional: bool = True,
    fetch_graph: bool = True,
) -> Contextualizer:
    """Factory function to create a configured Contextualizer.

    Args:
        memory_manager: Optional MemoryManager instance
        fetch_emotional: Whether to fetch emotional context
        fetch_graph: Whether to fetch graph relations

    Returns:
        Configured Contextualizer instance
    """
    config = ContextualizerConfig(
        fetch_emotional_context=fetch_emotional,
        fetch_graph_relations=fetch_graph,
    )
    return Contextualizer(config=config, memory_manager=memory_manager)
