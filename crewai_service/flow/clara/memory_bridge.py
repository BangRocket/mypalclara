"""Memory bridge - wrapper around MemoryManager for Flow integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from clara_core.memory import MemoryManager

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as OrmSession

    from .state import ConversationContext


class MemoryBridge:
    """Bridge between ClaraFlow and MemoryManager.

    Provides simplified methods for memory operations within the Flow context.
    """

    def __init__(self):
        """Initialize the bridge with the singleton MemoryManager."""
        self._mm = MemoryManager.get_instance()

    def fetch_context(
        self,
        context: "ConversationContext",
        user_message: str,
    ) -> tuple[list[str], list[str]]:
        """Fetch relevant memories from mem0.

        Args:
            context: Conversation context with user/channel info
            user_message: The current user message to search for

        Returns:
            Tuple of (user_memories, project_memories)
        """
        # Build project ID from context
        project_id = f"{context.user_id}-{context.guild_id or 'dm'}"

        return self._mm.fetch_mem0_context(
            user_id=context.user_id,
            project_id=project_id,
            user_message=user_message,
            participants=context.participants,
            is_dm=context.is_dm,
        )

    def store_exchange(
        self,
        db: "OrmSession",
        context: "ConversationContext",
        thread_id: str,
        user_message: str,
        assistant_reply: str,
    ) -> None:
        """Store the conversation exchange in mem0 for future recall.

        Args:
            db: Database session
            context: Conversation context
            thread_id: Thread ID for message retrieval
            user_message: The user's message
            assistant_reply: Clara's response
        """
        # Get recent messages for context
        recent_msgs = self._mm.get_recent_messages(db, thread_id)

        # Build project ID
        project_id = f"{context.user_id}-{context.guild_id or 'dm'}"

        self._mm.add_to_mem0(
            user_id=context.user_id,
            project_id=project_id,
            recent_msgs=recent_msgs,
            user_message=user_message,
            assistant_reply=assistant_reply,
            participants=context.participants,
            is_dm=context.is_dm,
        )

    def get_recent_messages(
        self,
        db: "OrmSession",
        thread_id: str,
    ) -> list[dict]:
        """Get recent messages from a thread as dicts.

        Args:
            db: Database session
            thread_id: Thread ID

        Returns:
            List of message dicts with role and content
        """
        msgs = self._mm.get_recent_messages(db, thread_id)
        return [{"role": m.role, "content": m.content} for m in msgs]

    def get_thread_summary(
        self,
        db: "OrmSession",
        thread_id: str,
    ) -> str | None:
        """Get the summary for a thread if it exists.

        Args:
            db: Database session
            thread_id: Thread ID

        Returns:
            Thread summary or None
        """
        thread = self._mm.get_thread(db, thread_id)
        if thread:
            return thread.summary
        return None

    def store_message(
        self,
        db: "OrmSession",
        thread_id: str,
        user_id: str,
        role: str,
        content: str,
    ) -> None:
        """Store a single message.

        Args:
            db: Database session
            thread_id: Thread ID
            user_id: User ID
            role: Message role (user/assistant)
            content: Message content
        """
        self._mm.store_message(db, thread_id, user_id, role, content)
