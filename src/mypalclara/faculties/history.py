"""
History Faculty - Chat history search and retrieval.

Provides tools for searching and retrieving past messages
from the current channel.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from mypalclara.faculties.base import Faculty
from mypalclara.models.state import FacultyResult

logger = logging.getLogger(__name__)


class HistoryFaculty(Faculty):
    """Chat history faculty."""

    name = "history"
    description = "Search and retrieve chat history from the current channel"

    available_actions = [
        "search",
        "get_recent",
        "get_from_user",
        "get_before",
    ]

    def __init__(self):
        self._channel = None  # Set by adapter when executing

    def set_channel(self, channel):
        """Set the Discord channel for history queries."""
        self._channel = channel

    async def execute(
        self,
        intent: str,
        constraints: Optional[list[str]] = None,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> FacultyResult:
        """Execute history-related intent."""
        logger.info(f"[history] Intent: {intent}")

        if self._channel is None:
            return FacultyResult(
                success=False,
                summary="Chat history requires a Discord channel context",
                error="No channel available",
            )

        try:
            action, params = self._parse_intent(intent)
            logger.info(f"[history] Action: {action}")

            if action == "search":
                result = await self._search(params)
            elif action == "get_recent":
                result = await self._get_recent(params)
            elif action == "get_from_user":
                result = await self._get_from_user(params)
            elif action == "get_before":
                result = await self._get_before(params)
            else:
                return FacultyResult(
                    success=False,
                    summary=f"Unknown history action: {action}",
                    error=f"Action '{action}' not recognized",
                )

            return result

        except Exception as e:
            logger.exception(f"[history] Error: {e}")
            return FacultyResult(
                success=False,
                summary=f"History error: {str(e)}",
                error=str(e),
            )

    def _parse_intent(self, intent: str) -> tuple[str, dict]:
        """Parse natural language intent into action and parameters."""
        intent_lower = intent.lower()

        # Search patterns
        if any(phrase in intent_lower for phrase in ["search for", "find", "look for", "search"]):
            query = self._extract_query(intent)
            from_user = self._extract_user(intent)
            return "search", {"query": query, "from_user": from_user}

        # Get from specific user
        if any(phrase in intent_lower for phrase in ["from user", "messages from", "said by"]):
            from_user = self._extract_user(intent)
            return "get_from_user", {"from_user": from_user}

        # Get before time
        if any(phrase in intent_lower for phrase in ["yesterday", "last week", "hours ago", "before"]):
            hours = self._extract_hours(intent)
            return "get_before", {"before_hours": hours}

        # Default to get recent
        count = self._extract_count(intent)
        return "get_recent", {"count": count}

    def _extract_query(self, text: str) -> str:
        """Extract search query from text."""
        import re
        # Look for quoted query
        match = re.search(r'["\']([^"\']+)["\']', text)
        if match:
            return match.group(1)

        # Extract after "search for" or "find"
        for phrase in ["search for", "find", "look for"]:
            if phrase in text.lower():
                idx = text.lower().find(phrase) + len(phrase)
                return text[idx:].strip()

        return text

    def _extract_user(self, text: str) -> str:
        """Extract username from text."""
        import re
        match = re.search(r'(?:from|by)\s+@?(\w+)', text, re.IGNORECASE)
        return match.group(1) if match else ""

    def _extract_count(self, text: str) -> int:
        """Extract message count from text."""
        import re
        match = re.search(r'(\d+)\s*(?:message|msg)', text, re.IGNORECASE)
        if match:
            return min(int(match.group(1)), 200)
        return 50

    def _extract_hours(self, text: str) -> int:
        """Extract hours from text."""
        import re

        if "yesterday" in text.lower():
            return 24

        if "last week" in text.lower():
            return 168

        match = re.search(r'(\d+)\s*(?:hour|hr)', text, re.IGNORECASE)
        if match:
            return int(match.group(1))

        match = re.search(r'(\d+)\s*(?:day)', text, re.IGNORECASE)
        if match:
            return int(match.group(1)) * 24

        return 24

    async def _search(self, params: dict) -> FacultyResult:
        """Search through chat history."""
        query = params.get("query", "").lower()
        if not query:
            return FacultyResult(success=False, summary="No search query provided", error="Missing query")

        from_user = params.get("from_user", "").lower()
        limit = params.get("limit", 500)

        matches = []
        count = 0

        async for msg in self._channel.history(limit=limit):
            count += 1
            content_lower = msg.content.lower()

            if query not in content_lower:
                continue

            if from_user:
                author_name = msg.author.display_name.lower()
                if from_user not in author_name:
                    continue

            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M")
            author = msg.author.display_name
            content = msg.content[:200] + ("..." if len(msg.content) > 200 else "")
            matches.append(f"[{timestamp}] **{author}:** {content}")

            if len(matches) >= 20:
                break

        if not matches:
            return FacultyResult(
                success=True,
                summary=f"No messages found matching '{params.get('query', '')}' in the last {count} messages.",
                data={"matches": [], "searched": count},
            )

        return FacultyResult(
            success=True,
            summary=f"Found {len(matches)} matching message(s):\n\n" + "\n\n".join(matches),
            data={"matches": matches, "count": len(matches), "searched": count},
        )

    async def _get_recent(self, params: dict) -> FacultyResult:
        """Get recent chat history."""
        count = min(params.get("count", 50), 200)

        messages = []
        async for msg in self._channel.history(limit=count):
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M")
            author = msg.author.display_name
            content = msg.content[:300] + ("..." if len(msg.content) > 300 else "")
            messages.append(f"[{timestamp}] **{author}:** {content}")

        if not messages:
            return FacultyResult(
                success=True,
                summary="No messages found in this channel.",
                data={"messages": []},
            )

        # Reverse to chronological order
        messages.reverse()

        return FacultyResult(
            success=True,
            summary=f"Chat history ({len(messages)} messages):\n\n" + "\n\n".join(messages),
            data={"messages": messages, "count": len(messages)},
        )

    async def _get_from_user(self, params: dict) -> FacultyResult:
        """Get messages from a specific user."""
        from_user = params.get("from_user", "").lower()
        if not from_user:
            return FacultyResult(success=False, summary="No user specified", error="Missing from_user")

        limit = params.get("limit", 200)
        messages = []

        async for msg in self._channel.history(limit=limit):
            author_name = msg.author.display_name.lower()
            if from_user not in author_name:
                continue

            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M")
            author = msg.author.display_name
            content = msg.content[:300] + ("..." if len(msg.content) > 300 else "")
            messages.append(f"[{timestamp}] **{author}:** {content}")

            if len(messages) >= 30:
                break

        if not messages:
            return FacultyResult(
                success=True,
                summary=f"No messages found from '{params.get('from_user', '')}'",
                data={"messages": []},
            )

        messages.reverse()

        return FacultyResult(
            success=True,
            summary=f"Messages from {params.get('from_user', '')} ({len(messages)}):\n\n" + "\n\n".join(messages),
            data={"messages": messages, "count": len(messages)},
        )

    async def _get_before(self, params: dict) -> FacultyResult:
        """Get messages from before a certain time."""
        before_hours = params.get("before_hours", 24)
        count = min(params.get("count", 50), 200)

        before = datetime.now(UTC) - timedelta(hours=before_hours)
        messages = []

        async for msg in self._channel.history(limit=count, before=before):
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M")
            author = msg.author.display_name
            content = msg.content[:300] + ("..." if len(msg.content) > 300 else "")
            messages.append(f"[{timestamp}] **{author}:** {content}")

        if not messages:
            return FacultyResult(
                success=True,
                summary=f"No messages found from {before_hours} hours ago.",
                data={"messages": []},
            )

        messages.reverse()

        return FacultyResult(
            success=True,
            summary=f"Messages from {before_hours}+ hours ago ({len(messages)}):\n\n" + "\n\n".join(messages),
            data={"messages": messages, "count": len(messages)},
        )
