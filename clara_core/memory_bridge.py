"""Memory system bridge for the new architecture.

Integrates Clara's MemoryManager with the channel plugin and routing systems.
Preserves all existing memory functionality while adding:
- Route-aware session management
- Channel-scoped context
- Plugin hook integration
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from config.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as OrmSession

    from clara_core.channels.types import MsgContext
    from clara_core.routing.resolve import AgentRoute

logger = get_logger("memory.bridge")


class MemoryBridge:
    """Bridges MemoryManager with the new channel/routing architecture.

    Provides:
    - Route-aware session creation using routing system's session keys
    - Channel-scoped memory context
    - Integration with plugin lifecycle hooks
    - Memory event forwarding to channel adapters
    """

    def __init__(self) -> None:
        """Initialize the memory bridge."""
        self._memory_manager = None
        self._on_memory_event: Callable[[str, dict[str, Any]], None] | None = None

    def initialize(
        self,
        llm_callable: Callable[[list[dict]], str],
        agent_id: str | None = None,
        on_memory_event: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        """Initialize the underlying MemoryManager.

        Args:
            llm_callable: Function that takes messages and returns LLM response
            agent_id: Bot persona identifier (default: from BOT_NAME env var or "clara")
            on_memory_event: Optional callback for memory events
        """
        from clara_core.memory import MemoryManager

        self._on_memory_event = on_memory_event
        self._memory_manager = MemoryManager.initialize(
            llm_callable=llm_callable,
            agent_id=agent_id,
            on_memory_event=self._handle_memory_event,
        )

    @property
    def manager(self) -> Any:
        """Get the underlying MemoryManager.

        Returns:
            The MemoryManager instance

        Raises:
            RuntimeError: If not initialized
        """
        if self._memory_manager is None:
            raise RuntimeError("MemoryBridge not initialized. Call initialize() first.")
        return self._memory_manager

    def _handle_memory_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Handle memory events and forward to channel adapters.

        Args:
            event_type: Type of memory event
            data: Event data
        """
        # Forward to registered callback
        if self._on_memory_event:
            self._on_memory_event(event_type, data)

        # Emit plugin hook
        try:
            import asyncio

            from clara_core.plugins import PluginHook, get_plugin_manager

            manager = get_plugin_manager()

            # Map memory events to plugin hooks
            if event_type == "memory_retrieved":
                asyncio.create_task(
                    manager.emit_hook(PluginHook.AGENT_START, memory_data=data)
                )
            elif event_type == "memory_extracted":
                asyncio.create_task(
                    manager.emit_hook(PluginHook.AGENT_END, memory_data=data)
                )
        except Exception:
            pass  # Plugin system may not be initialized

    def get_session_for_route(
        self,
        db: "OrmSession",
        route: "AgentRoute",
        context: "MsgContext",
    ) -> Any:
        """Get or create a session based on routing information.

        Uses the route's session_key for session isolation, combining
        the routing system's scoping with memory manager's session handling.

        Args:
            db: Database session
            route: The resolved agent route
            context: The message context

        Returns:
            Session object
        """
        # Build user_id with platform prefix
        user_id = f"{context.channel_type.value}-{context.user_id}"

        # Use route's session key as context_id for proper isolation
        context_id = route.session_key

        return self.manager.get_or_create_session(
            db=db,
            user_id=user_id,
            context_id=context_id,
        )

    def get_session_for_context(
        self,
        db: "OrmSession",
        context: "MsgContext",
    ) -> Any:
        """Get or create a session directly from message context.

        For use when routing is not available (e.g., CLI mode).

        Args:
            db: Database session
            context: The message context

        Returns:
            Session object
        """
        # Build user_id with platform prefix
        user_id = f"{context.channel_type.value}-{context.user_id}"

        # Build context_id from channel info
        if context.is_dm:
            context_id = f"dm-{context.user_id}"
        else:
            context_id = f"channel-{context.channel_id or 'default'}"

        return self.manager.get_or_create_session(
            db=db,
            user_id=user_id,
            context_id=context_id,
        )

    def fetch_context_for_message(
        self,
        user_id: str,
        project_id: str,
        user_message: str,
        context: "MsgContext",
    ) -> tuple[list[str], list[str], list[dict]]:
        """Fetch memory context for a message.

        Wraps MemoryManager.fetch_mem0_context with channel-aware parameters.

        Args:
            user_id: The user ID
            project_id: The project ID
            user_message: The user's message
            context: The message context for channel-specific handling

        Returns:
            Tuple of (user_memories, project_memories, graph_relations)
        """
        # Build participants from context metadata
        participants = context.metadata.get("participants", [])

        return self.manager.fetch_mem0_context(
            user_id=user_id,
            project_id=project_id,
            user_message=user_message,
            participants=participants,
            is_dm=context.is_dm,
        )

    def add_memory_for_message(
        self,
        user_id: str,
        project_id: str,
        recent_msgs: list[Any],
        user_message: str,
        assistant_reply: str,
        context: "MsgContext",
    ) -> None:
        """Add conversation to memory.

        Wraps MemoryManager.add_to_mem0 with channel-aware parameters.

        Args:
            user_id: The user ID
            project_id: The project ID
            recent_msgs: Recent message history
            user_message: The user's message
            assistant_reply: Clara's response
            context: The message context
        """
        # Build participants from context metadata
        participants = context.metadata.get("participants", [])

        self.manager.add_to_mem0(
            user_id=user_id,
            project_id=project_id,
            recent_msgs=recent_msgs,
            user_message=user_message,
            assistant_reply=assistant_reply,
            participants=participants,
            is_dm=context.is_dm,
        )

    def build_prompt_for_context(
        self,
        user_mems: list[str],
        proj_mems: list[str],
        thread_summary: str | None,
        recent_msgs: list[Any],
        user_message: str,
        context: "MsgContext",
        route: "AgentRoute | None" = None,
    ) -> list[dict[str, str]]:
        """Build prompt with full context.

        Wraps MemoryManager.build_prompt with route-aware customizations.

        Args:
            user_mems: User memories
            proj_mems: Project memories
            thread_summary: Optional thread summary
            recent_msgs: Recent messages
            user_message: Current user message
            context: Message context
            route: Optional resolved route for agent-specific prompts

        Returns:
            List of messages ready for LLM
        """
        # Get emotional context for session warmth
        user_id = f"{context.channel_type.value}-{context.user_id}"
        emotional_context = self.manager.fetch_emotional_context(user_id)

        # Get recurring topics
        recurring_topics = self.manager.fetch_topic_recurrence(user_id)

        # Build base prompt
        prompt = self.manager.build_prompt(
            user_mems=user_mems,
            proj_mems=proj_mems,
            thread_summary=thread_summary,
            recent_msgs=recent_msgs,
            user_message=user_message,
            emotional_context=emotional_context,
            recurring_topics=recurring_topics,
        )

        # Add route-specific system prompt if configured
        if route and route.binding.system_prompt:
            # Prepend agent-specific instructions
            prompt.insert(1, {
                "role": "system",
                "content": route.binding.system_prompt,
            })

        # Add channel context hint
        channel_hint = self._build_channel_hint(context)
        if channel_hint:
            prompt.insert(1, {
                "role": "system",
                "content": channel_hint,
            })

        return prompt

    def _build_channel_hint(self, context: "MsgContext") -> str | None:
        """Build a channel context hint for the prompt.

        Provides Clara with awareness of the communication channel.

        Args:
            context: The message context

        Returns:
            Channel hint string or None
        """
        parts = []

        # Channel type
        channel_name = context.channel_type.value
        if context.is_dm:
            parts.append(f"Currently in a direct message on {channel_name}.")
        elif context.guild_name:
            channel_display = context.metadata.get("channel_name", "")
            if channel_display:
                parts.append(
                    f"Currently in #{channel_display} on the {context.guild_name} server ({channel_name})."
                )
            else:
                parts.append(f"Currently on the {context.guild_name} server ({channel_name}).")

        if not parts:
            return None

        return " ".join(parts)


# Global bridge instance
_bridge: MemoryBridge | None = None


def get_memory_bridge() -> MemoryBridge:
    """Get the global memory bridge instance."""
    global _bridge
    if _bridge is None:
        _bridge = MemoryBridge()
    return _bridge


def reset_memory_bridge() -> None:
    """Reset the global memory bridge (for testing)."""
    global _bridge
    _bridge = None
