"""Chat history tools - Clara core tool.

Provides tools for searching and retrieving chat history.
Tools: search_chat_history, get_chat_history (Discord-specific)
       search_session_history, get_session_history (DB-backed, all platforms)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from tools._base import ToolContext, ToolDef

MODULE_NAME = "chat_history"
MODULE_VERSION = "2.0.0"

SYSTEM_PROMPT = """
## Chat History Search
You can search and retrieve past messages from conversations.

**Database Tools (all platforms):**
- `search_session_history` - Search your message database by keyword across sessions
- `get_session_history` - Get recent messages from the current or all sessions

**Discord-only Tools:**
- `search_chat_history` - Search the Discord channel's message history
- `get_chat_history` - Get recent Discord channel messages

**When to Use:**
- User asks about something discussed earlier → `search_session_history`
- User says "what did we talk about last week?" → `search_session_history`
- Looking up past conversations across sessions → `search_session_history`
- Need recent context from current conversation → `get_session_history`
- Need Discord-specific channel history (other users' messages) → Discord tools

**Note:** Database tools search Clara's own message history. Discord tools search
the full channel (including other users' messages not directed at Clara).
""".strip()


# Database session factory (set during initialization)
_session_factory = None


def _get_session():
    """Get a database session."""
    if _session_factory is None:
        raise RuntimeError("Chat history DB not initialized - no database connection")
    return _session_factory()


# --- Discord Tool Handlers (existing) ---


async def search_chat_history(args: dict[str, Any], ctx: ToolContext) -> str:
    """Search through chat history for messages matching a query."""
    query = args.get("query", "").lower()
    if not query:
        return "Error: No search query provided"

    limit = min(args.get("limit", 200), 1000)
    from_user = args.get("from_user", "").lower()

    # Get the Discord channel from context
    channel = ctx.extra.get("channel")
    if channel is None:
        return "Error: Chat history search requires a Discord channel context"

    try:
        matches = []
        count = 0

        async for msg in channel.history(limit=limit):
            count += 1
            content_lower = msg.content.lower()

            # Check if matches query
            if query not in content_lower:
                continue

            # Check user filter
            if from_user:
                author_name = msg.author.display_name.lower()
                if from_user not in author_name and from_user not in str(msg.author.id):
                    continue

            # Format match
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M")
            author = msg.author.display_name
            content = msg.content[:200] + ("..." if len(msg.content) > 200 else "")
            matches.append(f"[{timestamp}] **{author}:** {content}")

            if len(matches) >= 20:  # Cap results
                break

        if not matches:
            return f"No messages found matching '{args.get('query', '')}' in the last {count} messages."

        result = f"Found {len(matches)} matching message(s):\n\n"
        result += "\n\n".join(matches)
        return result

    except Exception as e:
        return f"Error searching chat history: {str(e)}"


async def get_chat_history(args: dict[str, Any], ctx: ToolContext) -> str:
    """Retrieve recent chat history."""
    count = min(args.get("count", 50), 200)
    before_hours = args.get("before_hours")
    user_filter = args.get("user_filter", "").lower()

    # Get the Discord channel from context
    channel = ctx.extra.get("channel")
    if channel is None:
        return "Error: Chat history retrieval requires a Discord channel context"

    try:
        # Calculate before time if specified
        before = None
        if before_hours:
            before = datetime.now(UTC) - timedelta(hours=before_hours)

        messages = []
        async for msg in channel.history(limit=count, before=before):
            # Apply user filter
            if user_filter:
                author_name = msg.author.display_name.lower()
                if user_filter not in author_name:
                    continue

            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M")
            author = msg.author.display_name
            content = msg.content[:300] + ("..." if len(msg.content) > 300 else "")
            messages.append(f"[{timestamp}] **{author}:** {content}")

        if not messages:
            return "No messages found in the specified time range."

        # Reverse to chronological order
        messages.reverse()

        result = f"Chat history ({len(messages)} messages):\n\n"
        result += "\n\n".join(messages)
        return result

    except Exception as e:
        return f"Error retrieving chat history: {str(e)}"


# --- Database Tool Handlers (new, all platforms) ---


async def search_session_history(args: dict[str, Any], ctx: ToolContext) -> str:
    """Search Clara's message database by keyword across sessions."""
    from db.models import Message, Session

    query = args.get("query", "").strip()
    if not query:
        return "Error: No search query provided"

    limit = min(args.get("limit", 20), 50)
    days_back = min(args.get("days_back", 30), 365)
    role_filter = args.get("role", "")

    try:
        session = _get_session()
        try:
            since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days_back)

            # Get all session IDs for this user
            user_sessions = session.query(Session.id).filter(Session.user_id == ctx.user_id).all()
            session_ids = [s.id for s in user_sessions]

            if not session_ids:
                return "No conversation history found."

            q = session.query(Message).filter(
                Message.session_id.in_(session_ids),
                Message.created_at >= since,
                Message.content.ilike(f"%{query}%"),
            )

            if role_filter and role_filter in ("user", "assistant"):
                q = q.filter(Message.role == role_filter)

            messages = q.order_by(Message.created_at.desc()).limit(limit).all()

            if not messages:
                return f"No messages found matching '{query}' in the last {days_back} days."

            result = f"Found {len(messages)} matching message(s):\n\n"
            for msg in messages:
                ts = msg.created_at.strftime("%Y-%m-%d %H:%M")
                role_label = "You" if msg.role == "assistant" else "User"
                content = msg.content[:200] + ("..." if len(msg.content) > 200 else "")
                result += f"[{ts}] **{role_label}:** {content}\n\n"

            return result.rstrip()

        finally:
            session.close()

    except RuntimeError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error searching session history: {e}"


async def get_session_history(args: dict[str, Any], ctx: ToolContext) -> str:
    """Get recent messages from Clara's database."""
    from db.models import Message, Session

    count = min(args.get("count", 20), 100)
    days_back = min(args.get("days_back", 7), 365)
    role_filter = args.get("role", "")
    all_sessions = args.get("all_sessions", False)

    try:
        session = _get_session()
        try:
            since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days_back)

            if all_sessions:
                # Get all session IDs for this user
                user_sessions = session.query(Session.id).filter(Session.user_id == ctx.user_id).all()
                session_ids = [s.id for s in user_sessions]
            else:
                # Get most recent active session
                recent_session = (
                    session.query(Session)
                    .filter(
                        Session.user_id == ctx.user_id,
                        Session.archived != "true",
                    )
                    .order_by(Session.last_activity_at.desc())
                    .first()
                )
                session_ids = [recent_session.id] if recent_session else []

            if not session_ids:
                return "No conversation history found."

            q = session.query(Message).filter(
                Message.session_id.in_(session_ids),
                Message.created_at >= since,
            )

            if role_filter and role_filter in ("user", "assistant"):
                q = q.filter(Message.role == role_filter)

            messages = q.order_by(Message.created_at.desc()).limit(count).all()

            if not messages:
                scope = "any session" if all_sessions else "the current session"
                return f"No messages found in {scope} within the last {days_back} days."

            # Reverse to chronological order
            messages.reverse()

            scope_label = "all sessions" if all_sessions else "current session"
            result = f"Recent messages ({scope_label}, {len(messages)} messages):\n\n"
            for msg in messages:
                ts = msg.created_at.strftime("%Y-%m-%d %H:%M")
                role_label = "You" if msg.role == "assistant" else "User"
                content = msg.content[:300] + ("..." if len(msg.content) > 300 else "")
                result += f"[{ts}] **{role_label}:** {content}\n\n"

            return result.rstrip()

        finally:
            session.close()

    except RuntimeError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error retrieving session history: {e}"


# --- Tool Definitions ---

TOOLS = [
    # Discord-specific tools
    ToolDef(
        name="search_chat_history",
        description=(
            "Search through the full chat history for messages matching a query. "
            "Use this to find past conversations, recall what was discussed, "
            "or find specific messages. Searches message content."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text to search for in message content",
                },
                "limit": {
                    "type": "integer",
                    "description": ("Maximum messages to search through (default: 200, max: 1000)"),
                },
                "from_user": {
                    "type": "string",
                    "description": "Optional: only search messages from this username",
                },
            },
            "required": ["query"],
        },
        handler=search_chat_history,
        platforms=["discord"],  # Discord-specific
    ),
    ToolDef(
        name="get_chat_history",
        description=(
            "Retrieve recent chat history beyond what's in the current context. "
            "Use this to get a summary of past conversations or see what was "
            "discussed earlier. Returns messages in chronological order."
        ),
        parameters={
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": ("Number of messages to retrieve (default: 50, max: 200)"),
                },
                "before_hours": {
                    "type": "number",
                    "description": (
                        "Only get messages older than this many hours ago. "
                        "Useful for looking at 'yesterday' or 'last week'."
                    ),
                },
                "user_filter": {
                    "type": "string",
                    "description": "Optional: only include messages from this username",
                },
            },
            "required": [],
        },
        handler=get_chat_history,
        platforms=["discord"],  # Discord-specific
    ),
    # Database-backed tools (all platforms)
    ToolDef(
        name="search_session_history",
        description=(
            "Search Clara's own message database by keyword across all sessions for this user. "
            "Use this to recall past conversations, find what was discussed, "
            "or look up specific topics from previous sessions. "
            "Works on all platforms (not just Discord)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text to search for in message content",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results to return (default: 20, max: 50)",
                },
                "days_back": {
                    "type": "integer",
                    "description": "How many days back to search (default: 30, max: 365)",
                },
                "role": {
                    "type": "string",
                    "enum": ["user", "assistant"],
                    "description": "Optional: filter by message role (user or assistant)",
                },
            },
            "required": ["query"],
        },
        handler=search_session_history,
    ),
    ToolDef(
        name="get_session_history",
        description=(
            "Get recent messages from Clara's database. By default returns messages "
            "from the current session. Set all_sessions=true to include all sessions. "
            "Works on all platforms (not just Discord)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Number of messages to retrieve (default: 20, max: 100)",
                },
                "days_back": {
                    "type": "integer",
                    "description": "How many days back to look (default: 7, max: 365)",
                },
                "role": {
                    "type": "string",
                    "enum": ["user", "assistant"],
                    "description": "Optional: filter by message role (user or assistant)",
                },
                "all_sessions": {
                    "type": "boolean",
                    "description": "If true, include messages from all sessions (default: false)",
                },
            },
            "required": [],
        },
        handler=get_session_history,
    ),
]


# --- Lifecycle Hooks ---


async def initialize() -> None:
    """Initialize chat history module with database connection."""
    global _session_factory

    try:
        from db import SessionLocal

        _session_factory = SessionLocal
    except Exception:
        pass  # Database not available, DB tools will return error when used


async def cleanup() -> None:
    """Cleanup on module unload."""
    global _session_factory
    _session_factory = None
