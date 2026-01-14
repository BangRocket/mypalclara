#!/usr/bin/env python3
"""
Memory Administration TUI for MyPalClara.

A comprehensive terminal user interface for managing memories in the MyPalClara system.
Supports full CRUD operations on both PostgreSQL (main app DB) and pgvector (mem0) databases.

Usage:
    poetry run python -m scripts.memory_admin_tui

Features:
    - Browse and search memories with filtering by user, type, project
    - View full memory details including metadata and embeddings info
    - Create new memories with type classification
    - Edit existing memory content and metadata
    - Delete memories with confirmation
    - Browse users, projects, and sessions from main DB
    - Real-time database connection status

Environment Variables:
    DATABASE_URL      - PostgreSQL connection for main app DB
    MEM0_DATABASE_URL - PostgreSQL+pgvector connection for memories
    OPENAI_API_KEY    - Required for mem0 embeddings
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Markdown,
    OptionList,
    RadioButton,
    RadioSet,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)
from textual.widgets.option_list import Option

if TYPE_CHECKING:
    from vendor.mem0 import Memory


# =============================================================================
# Database Connection Managers
# =============================================================================


@dataclass
class ConnectionStatus:
    """Database connection status."""

    connected: bool
    message: str
    db_type: str  # "main" or "mem0"


class DatabaseManager:
    """Manages connections to both PostgreSQL databases."""

    def __init__(self):
        self.main_db_status: ConnectionStatus | None = None
        self.mem0_status: ConnectionStatus | None = None
        self._mem0: "Memory | None" = None
        self._session_local = None

    def connect_main_db(self) -> ConnectionStatus:
        """Connect to the main application database."""
        try:
            from sqlalchemy import text

            from db import DATABASE_URL, SessionLocal, engine

            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            self._session_local = SessionLocal

            db_type = "PostgreSQL" if "postgres" in DATABASE_URL else "SQLite"
            self.main_db_status = ConnectionStatus(connected=True, message=f"Connected to {db_type}", db_type="main")
        except Exception as e:
            self.main_db_status = ConnectionStatus(connected=False, message=f"Error: {str(e)[:50]}", db_type="main")
        return self.main_db_status

    def connect_mem0(self) -> ConnectionStatus:
        """Connect to the mem0 vector database."""
        try:
            from config.mem0 import MEM0, MEM0_COLLECTION_NAME, MEM0_DATABASE_URL

            if MEM0 is None:
                self.mem0_status = ConnectionStatus(
                    connected=False, message="mem0 not initialized (check OPENAI_API_KEY)", db_type="mem0"
                )
            else:
                self._mem0 = MEM0
                db_type = "pgvector" if MEM0_DATABASE_URL else "Qdrant"
                self.mem0_status = ConnectionStatus(
                    connected=True, message=f"Connected to {db_type} ({MEM0_COLLECTION_NAME})", db_type="mem0"
                )
        except Exception as e:
            self.mem0_status = ConnectionStatus(connected=False, message=f"Error: {str(e)[:50]}", db_type="mem0")
        return self.mem0_status

    def get_session(self):
        """Get a database session for main DB."""
        if self._session_local:
            return self._session_local()
        return None

    @property
    def mem0(self) -> "Memory | None":
        """Get the mem0 Memory instance."""
        return self._mem0

    def get_all_users(self) -> list[str]:
        """Get all unique user IDs from the main database."""
        session = self.get_session()
        if not session:
            return []
        try:
            from db.models import Session as DBSession

            users = session.query(DBSession.user_id).distinct().all()
            return sorted([u[0] for u in users if u[0]])
        except Exception:
            return []
        finally:
            session.close()

    def get_all_projects(self) -> list[tuple[str, str, str]]:
        """Get all projects from the main database.

        Returns list of (id, name, owner_id) tuples.
        """
        session = self.get_session()
        if not session:
            return []
        try:
            from db.models import Project

            projects = session.query(Project).all()
            return [(p.id, p.name, p.owner_id) for p in projects]
        except Exception:
            return []
        finally:
            session.close()

    def get_sessions_for_user(self, user_id: str) -> list[dict]:
        """Get all sessions for a user."""
        session = self.get_session()
        if not session:
            return []
        try:
            from db.models import Session as DBSession

            sessions = (
                session.query(DBSession)
                .filter(DBSession.user_id == user_id)
                .order_by(DBSession.last_activity_at.desc())
                .all()
            )
            return [
                {
                    "id": s.id,
                    "title": s.title or "Untitled",
                    "started_at": s.started_at,
                    "last_activity": s.last_activity_at,
                    "archived": s.archived == "true",
                    "has_summary": bool(s.session_summary),
                }
                for s in sessions
            ]
        except Exception:
            return []
        finally:
            session.close()

    def get_memories_for_user(
        self,
        user_id: str,
        limit: int = 100,
        memory_type: str | None = None,
        project_id: str | None = None,
    ) -> list[dict]:
        """Get all memories for a user from mem0."""
        if not self._mem0:
            return []

        try:
            # Use get_all with filters
            filters = {}
            if memory_type:
                filters["memory_type"] = memory_type
            if project_id:
                filters["project_id"] = project_id

            result = self._mem0.get_all(
                user_id=user_id,
                limit=limit,
            )
            memories = result.get("results", [])

            # Convert to consistent format
            formatted = []
            for mem in memories:
                metadata = mem.get("metadata", {})
                payload = mem.get("payload", {})

                # Get memory_type from metadata or payload
                mem_type = metadata.get("memory_type") or payload.get("memory_type", "unknown")

                # Apply type filter if specified (mem0 get_all doesn't support filters)
                if memory_type and mem_type != memory_type:
                    continue

                # Apply project filter
                mem_project = metadata.get("project_id") or payload.get("project_id")
                if project_id and mem_project != project_id:
                    continue

                formatted.append(
                    {
                        "id": mem.get("id", ""),
                        "content": mem.get("memory", payload.get("data", "")),
                        "memory_type": mem_type,
                        "user_id": mem.get("user_id", user_id),
                        "project_id": mem_project,
                        "created_at": mem.get("created_at") or payload.get("created_at"),
                        "updated_at": mem.get("updated_at") or payload.get("updated_at"),
                        "metadata": metadata,
                        "payload": payload,
                    }
                )

            return formatted
        except Exception as e:
            print(f"Error fetching memories: {e}")
            return []

    def search_memories(
        self,
        query: str,
        user_id: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Search memories using vector similarity."""
        if not self._mem0:
            return []

        try:
            kwargs = {"query": query, "limit": limit}
            if user_id:
                kwargs["user_id"] = user_id

            result = self._mem0.search(**kwargs)
            memories = result.get("results", [])

            formatted = []
            for mem in memories:
                metadata = mem.get("metadata", {})
                payload = mem.get("payload", {})

                formatted.append(
                    {
                        "id": mem.get("id", ""),
                        "content": mem.get("memory", payload.get("data", "")),
                        "memory_type": metadata.get("memory_type") or payload.get("memory_type", "unknown"),
                        "user_id": mem.get("user_id", ""),
                        "project_id": metadata.get("project_id") or payload.get("project_id"),
                        "created_at": mem.get("created_at") or payload.get("created_at"),
                        "updated_at": mem.get("updated_at") or payload.get("updated_at"),
                        "score": mem.get("score", 0),
                        "metadata": metadata,
                        "payload": payload,
                    }
                )

            return formatted
        except Exception as e:
            print(f"Error searching memories: {e}")
            return []

    def get_memory(self, memory_id: str) -> dict | None:
        """Get a single memory by ID."""
        if not self._mem0:
            return None

        try:
            result = self._mem0.get(memory_id)
            if result:
                metadata = result.get("metadata", {})
                payload = result.get("payload", {})
                return {
                    "id": result.get("id", memory_id),
                    "content": result.get("memory", payload.get("data", "")),
                    "memory_type": metadata.get("memory_type") or payload.get("memory_type", "unknown"),
                    "user_id": result.get("user_id", ""),
                    "project_id": metadata.get("project_id") or payload.get("project_id"),
                    "created_at": result.get("created_at") or payload.get("created_at"),
                    "updated_at": result.get("updated_at") or payload.get("updated_at"),
                    "metadata": metadata,
                    "payload": payload,
                }
            return None
        except Exception as e:
            print(f"Error fetching memory: {e}")
            return None

    def create_memory(
        self,
        content: str,
        user_id: str,
        memory_type: str = "active",
        project_id: str | None = None,
        infer: bool = False,
    ) -> dict | None:
        """Create a new memory.

        Args:
            content: Memory content
            user_id: User ID to associate with
            memory_type: stable, active, or ephemeral
            project_id: Optional project ID
            infer: If True, use LLM to extract facts. If False, store directly.

        Returns:
            Result dict or None on error
        """
        if not self._mem0:
            return None

        try:
            metadata = {"memory_type": memory_type}
            if project_id:
                metadata["project_id"] = project_id

            result = self._mem0.add(
                content,
                user_id=user_id,
                metadata=metadata,
                infer=infer,
            )
            return result
        except Exception as e:
            print(f"Error creating memory: {e}")
            return None

    def update_memory(self, memory_id: str, content: str) -> bool:
        """Update a memory's content."""
        if not self._mem0:
            return False

        try:
            self._mem0.update(memory_id, content)
            return True
        except Exception as e:
            print(f"Error updating memory: {e}")
            return False

    def update_memory_metadata(
        self,
        memory_id: str,
        metadata: dict,
    ) -> bool:
        """Update a memory's metadata directly."""
        if not self._mem0:
            return False

        try:
            self._mem0.vector_store.update(
                vector_id=memory_id,
                vector=None,  # Keep existing embedding
                payload=metadata,
            )
            return True
        except Exception as e:
            print(f"Error updating metadata: {e}")
            return False

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory."""
        if not self._mem0:
            return False

        try:
            self._mem0.delete(memory_id)
            return True
        except Exception as e:
            print(f"Error deleting memory: {e}")
            return False

    def delete_all_user_memories(self, user_id: str) -> int:
        """Delete all memories for a user."""
        if not self._mem0:
            return 0

        try:
            result = self._mem0.delete_all(user_id=user_id)
            return result.get("deleted", 0) if isinstance(result, dict) else 0
        except Exception as e:
            print(f"Error deleting memories: {e}")
            return 0

    def get_memory_stats(self, user_id: str | None = None) -> dict:
        """Get memory statistics."""
        if not self._mem0:
            return {"error": "mem0 not connected"}

        try:
            if user_id:
                memories = self.get_memories_for_user(user_id, limit=10000)
            else:
                # Get all users and aggregate
                users = self.get_all_users()
                memories = []
                for uid in users:
                    memories.extend(self.get_memories_for_user(uid, limit=10000))

            # Calculate stats
            total = len(memories)
            by_type = {}
            by_user = {}
            by_project = {}

            for mem in memories:
                # By type
                mem_type = mem.get("memory_type", "unknown")
                by_type[mem_type] = by_type.get(mem_type, 0) + 1

                # By user
                uid = mem.get("user_id", "unknown")
                by_user[uid] = by_user.get(uid, 0) + 1

                # By project
                pid = mem.get("project_id") or "none"
                by_project[pid] = by_project.get(pid, 0) + 1

            return {
                "total": total,
                "by_type": by_type,
                "by_user": by_user,
                "by_project": by_project,
            }
        except Exception as e:
            return {"error": str(e)}


# =============================================================================
# Modal Screens
# =============================================================================


class ConfirmDialog(ModalScreen[bool]):
    """Confirmation dialog modal."""

    def __init__(self, title: str, message: str):
        super().__init__()
        self.dialog_title = title
        self.dialog_message = message

    def compose(self) -> ComposeResult:
        with Container(id="confirm-dialog"):
            yield Label(self.dialog_title, id="dialog-title")
            yield Static(self.dialog_message, id="dialog-message")
            with Horizontal(id="dialog-buttons"):
                yield Button("Cancel", id="cancel", variant="default")
                yield Button("Confirm", id="confirm", variant="error")

    @on(Button.Pressed, "#cancel")
    def cancel(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#confirm")
    def confirm(self) -> None:
        self.dismiss(True)


class MemoryDetailScreen(ModalScreen):
    """Screen showing full memory details."""

    def __init__(self, memory: dict):
        super().__init__()
        self.memory = memory

    def compose(self) -> ComposeResult:
        mem = self.memory

        # Format timestamps
        created = mem.get("created_at", "Unknown")
        updated = mem.get("updated_at", "Unknown")

        # Build detail markdown
        detail_md = f"""# Memory Details

**ID:** `{mem.get("id", "N/A")}`

**User:** {mem.get("user_id", "N/A")}

**Type:** {mem.get("memory_type", "unknown")}

**Project:** {mem.get("project_id", "None")}

**Created:** {created}

**Updated:** {updated}

---

## Content

{mem.get("content", "No content")}

---

## Metadata

```
{self._format_dict(mem.get("metadata", {}))}
```

## Payload

```
{self._format_dict(mem.get("payload", {}))}
```
"""

        with Container(id="memory-detail"):
            yield VerticalScroll(Markdown(detail_md))
            with Horizontal(id="detail-buttons"):
                yield Button("Close", id="close", variant="primary")

    def _format_dict(self, d: dict) -> str:
        """Format a dict for display."""
        if not d:
            return "(empty)"
        lines = []
        for k, v in d.items():
            if isinstance(v, str) and len(v) > 100:
                v = v[:100] + "..."
            lines.append(f"{k}: {v}")
        return "\n".join(lines)

    @on(Button.Pressed, "#close")
    def close_screen(self) -> None:
        self.dismiss()


class CreateMemoryScreen(ModalScreen[dict | None]):
    """Screen for creating a new memory."""

    def __init__(self, db_manager: DatabaseManager, default_user: str = ""):
        super().__init__()
        self.db_manager = db_manager
        self.default_user = default_user

    def compose(self) -> ComposeResult:
        users = self.db_manager.get_all_users()
        user_options = [(u, u) for u in users]
        if not user_options:
            user_options = [("demo-user", "demo-user")]

        with Container(id="create-memory"):
            yield Label("Create New Memory", id="create-title")

            yield Label("User ID:")
            yield Select(
                user_options,
                id="user-select",
                value=self.default_user or (users[0] if users else "demo-user"),
            )

            yield Label("Memory Type:")
            with RadioSet(id="type-radio"):
                yield RadioButton("Stable (identity, preferences)", id="stable", value=True)
                yield RadioButton("Active (projects, current work)", id="active")
                yield RadioButton("Ephemeral (temporary states)", id="ephemeral")

            yield Label("Content:")
            yield TextArea(id="content-input", language=None)

            yield Label("Project ID (optional):")
            yield Input(id="project-input", placeholder="Leave empty for no project")

            with Horizontal(id="create-buttons"):
                yield Button("Cancel", id="cancel", variant="default")
                yield Button("Create", id="create", variant="success")

    @on(Button.Pressed, "#cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#create")
    def create_memory(self) -> None:
        user_id = self.query_one("#user-select", Select).value
        content = self.query_one("#content-input", TextArea).text
        project_id = self.query_one("#project-input", Input).value or None

        # Get selected type
        radio_set = self.query_one("#type-radio", RadioSet)
        memory_type = "active"  # default
        if radio_set.pressed_button:
            btn_id = radio_set.pressed_button.id
            if btn_id == "stable":
                memory_type = "stable"
            elif btn_id == "ephemeral":
                memory_type = "ephemeral"

        if not content.strip():
            self.notify("Content cannot be empty", severity="error")
            return

        self.dismiss(
            {
                "user_id": user_id,
                "content": content,
                "memory_type": memory_type,
                "project_id": project_id,
            }
        )


class EditMemoryScreen(ModalScreen[dict | None]):
    """Screen for editing an existing memory."""

    def __init__(self, memory: dict):
        super().__init__()
        self.memory = memory

    def compose(self) -> ComposeResult:
        mem = self.memory
        current_type = mem.get("memory_type", "active")

        with Container(id="edit-memory"):
            yield Label(f"Edit Memory: {mem.get('id', '')[:8]}...", id="edit-title")

            yield Label(f"User: {mem.get('user_id', 'N/A')}")

            yield Label("Memory Type:")
            with RadioSet(id="type-radio"):
                yield RadioButton(
                    "Stable (identity, preferences)",
                    id="stable",
                    value=(current_type == "stable"),
                )
                yield RadioButton(
                    "Active (projects, current work)",
                    id="active",
                    value=(current_type == "active"),
                )
                yield RadioButton(
                    "Ephemeral (temporary states)",
                    id="ephemeral",
                    value=(current_type == "ephemeral"),
                )

            yield Label("Content:")
            yield TextArea(mem.get("content", ""), id="content-input", language=None)

            with Horizontal(id="edit-buttons"):
                yield Button("Cancel", id="cancel", variant="default")
                yield Button("Save", id="save", variant="success")

    @on(Button.Pressed, "#cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#save")
    def save_memory(self) -> None:
        content = self.query_one("#content-input", TextArea).text

        # Get selected type
        radio_set = self.query_one("#type-radio", RadioSet)
        memory_type = self.memory.get("memory_type", "active")
        if radio_set.pressed_button:
            btn_id = radio_set.pressed_button.id
            if btn_id in ("stable", "active", "ephemeral"):
                memory_type = btn_id

        if not content.strip():
            self.notify("Content cannot be empty", severity="error")
            return

        self.dismiss(
            {
                "id": self.memory.get("id"),
                "content": content,
                "memory_type": memory_type,
            }
        )


# =============================================================================
# Main Application
# =============================================================================


class MemoryAdminApp(App):
    """Memory Administration TUI Application."""

    TITLE = "Clara Memory Admin"
    SUB_TITLE = "Manage memories in PostgreSQL + pgvector"

    CSS = """
    /* Global styles */
    Screen {
        background: $surface;
    }

    /* Status bar */
    #status-bar {
        dock: top;
        height: 3;
        background: $primary-background;
        padding: 0 1;
    }

    .status-item {
        width: auto;
        padding: 0 2;
    }

    .status-connected {
        color: $success;
    }

    .status-disconnected {
        color: $error;
    }

    /* Main content */
    #main-content {
        height: 100%;
    }

    /* Sidebar */
    #sidebar {
        width: 30;
        background: $surface-darken-1;
        border-right: solid $primary;
    }

    #user-list {
        height: 1fr;
    }

    /* Memory table */
    #memory-container {
        width: 1fr;
    }

    #memory-table {
        height: 1fr;
    }

    /* Toolbar */
    #toolbar {
        dock: top;
        height: 3;
        background: $surface-darken-2;
        padding: 0 1;
    }

    #toolbar Button {
        margin-right: 1;
    }

    /* Search */
    #search-container {
        dock: top;
        height: 3;
        padding: 0 1;
    }

    #search-input {
        width: 50;
    }

    /* Filter bar */
    #filter-bar {
        dock: top;
        height: 3;
        padding: 0 1;
    }

    #type-filter {
        width: 20;
    }

    /* Stats panel */
    #stats-panel {
        height: auto;
        max-height: 15;
        background: $surface-darken-1;
        padding: 1;
        border-top: solid $primary;
    }

    /* Modal dialogs */
    #confirm-dialog {
        width: 50;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: solid $primary;
    }

    #dialog-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #dialog-message {
        margin-bottom: 1;
    }

    #dialog-buttons {
        align: center middle;
    }

    #dialog-buttons Button {
        margin: 0 1;
    }

    /* Memory detail */
    #memory-detail {
        width: 80%;
        height: 80%;
        background: $surface;
        border: solid $primary;
        padding: 1;
    }

    #detail-buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }

    /* Create/Edit memory */
    #create-memory, #edit-memory {
        width: 70;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    #create-title, #edit-title {
        text-style: bold;
        margin-bottom: 1;
    }

    #content-input {
        height: 10;
        margin-bottom: 1;
    }

    #create-buttons, #edit-buttons {
        align: center middle;
        margin-top: 1;
    }

    #create-buttons Button, #edit-buttons Button {
        margin: 0 1;
    }

    /* Tabs */
    TabbedContent {
        height: 100%;
    }

    TabPane {
        padding: 0;
    }

    /* Log panel */
    #log-panel {
        height: 10;
        background: $surface-darken-2;
        border-top: solid $primary;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("n", "new_memory", "New Memory"),
        Binding("d", "delete_memory", "Delete"),
        Binding("e", "edit_memory", "Edit"),
        Binding("s", "focus_search", "Search"),
        Binding("/", "focus_search", "Search"),
        Binding("f1", "show_help", "Help"),
    ]

    # Reactive state
    selected_user: reactive[str | None] = reactive(None)
    selected_memory_id: reactive[str | None] = reactive(None)
    memories: reactive[list[dict]] = reactive([])

    def __init__(self):
        super().__init__()
        self.db_manager = DatabaseManager()

    def compose(self) -> ComposeResult:
        yield Header()

        # Status bar
        with Horizontal(id="status-bar"):
            yield Static("Main DB: Connecting...", id="main-status", classes="status-item")
            yield Static("Mem0: Connecting...", id="mem0-status", classes="status-item")

        # Main content with tabs
        with TabbedContent():
            with TabPane("Memories", id="memories-tab"):
                with Horizontal(id="main-content"):
                    # Sidebar with users
                    with Vertical(id="sidebar"):
                        yield Label("Users", id="users-label")
                        yield ListView(id="user-list")

                    # Memory list
                    with Vertical(id="memory-container"):
                        # Toolbar
                        with Horizontal(id="toolbar"):
                            yield Button("New", id="btn-new", variant="success")
                            yield Button("Edit", id="btn-edit", variant="primary")
                            yield Button("Delete", id="btn-delete", variant="error")
                            yield Button("View", id="btn-view", variant="default")
                            yield Button("Refresh", id="btn-refresh", variant="default")

                        # Search
                        with Horizontal(id="search-container"):
                            yield Input(placeholder="Search memories...", id="search-input")
                            yield Button("Search", id="btn-search")
                            yield Button("Clear", id="btn-clear-search")

                        # Filter bar
                        with Horizontal(id="filter-bar"):
                            yield Label("Filter by type: ")
                            yield Select(
                                [
                                    ("All Types", "all"),
                                    ("Stable", "stable"),
                                    ("Active", "active"),
                                    ("Ephemeral", "ephemeral"),
                                ],
                                id="type-filter",
                                value="all",
                            )

                        # Memory table
                        yield DataTable(id="memory-table")

            with TabPane("Statistics", id="stats-tab"):
                yield VerticalScroll(Markdown("Loading statistics...", id="stats-content"))

            with TabPane("Sessions", id="sessions-tab"):
                with Horizontal():
                    with Vertical(id="session-sidebar", classes="sidebar"):
                        yield Label("Users")
                        yield ListView(id="session-user-list")
                    yield DataTable(id="sessions-table")

            with TabPane("Projects", id="projects-tab"):
                yield DataTable(id="projects-table")

        # Log panel
        yield RichLog(id="log-panel", highlight=True, markup=True)

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the application."""
        self.log_message("Starting Memory Admin TUI...")

        # Connect to databases
        self.connect_databases()

        # Setup tables
        self.setup_tables()

        # Load initial data
        self.load_users()
        self.load_projects()
        self.refresh_stats()

    def log_message(self, message: str, level: str = "info") -> None:
        """Log a message to the log panel."""
        log = self.query_one("#log-panel", RichLog)
        timestamp = datetime.now().strftime("%H:%M:%S")

        if level == "error":
            log.write(f"[red][{timestamp}] ERROR: {message}[/red]")
        elif level == "warning":
            log.write(f"[yellow][{timestamp}] WARN: {message}[/yellow]")
        elif level == "success":
            log.write(f"[green][{timestamp}] {message}[/green]")
        else:
            log.write(f"[dim][{timestamp}][/dim] {message}")

    def connect_databases(self) -> None:
        """Connect to both databases."""
        # Main DB
        status = self.db_manager.connect_main_db()
        main_label = self.query_one("#main-status", Static)
        if status.connected:
            main_label.update(f"Main DB: {status.message}")
            main_label.set_class(True, "status-connected")
            main_label.set_class(False, "status-disconnected")
            self.log_message(f"Main DB: {status.message}", "success")
        else:
            main_label.update(f"Main DB: {status.message}")
            main_label.set_class(False, "status-connected")
            main_label.set_class(True, "status-disconnected")
            self.log_message(f"Main DB: {status.message}", "error")

        # Mem0
        status = self.db_manager.connect_mem0()
        mem0_label = self.query_one("#mem0-status", Static)
        if status.connected:
            mem0_label.update(f"Mem0: {status.message}")
            mem0_label.set_class(True, "status-connected")
            mem0_label.set_class(False, "status-disconnected")
            self.log_message(f"Mem0: {status.message}", "success")
        else:
            mem0_label.update(f"Mem0: {status.message}")
            mem0_label.set_class(False, "status-connected")
            mem0_label.set_class(True, "status-disconnected")
            self.log_message(f"Mem0: {status.message}", "error")

    def setup_tables(self) -> None:
        """Setup data table columns."""
        # Memory table
        table = self.query_one("#memory-table", DataTable)
        table.add_columns("ID", "Content", "Type", "Project", "Updated")
        table.cursor_type = "row"

        # Sessions table
        sessions_table = self.query_one("#sessions-table", DataTable)
        sessions_table.add_columns("ID", "Title", "Started", "Last Activity", "Archived", "Summary")
        sessions_table.cursor_type = "row"

        # Projects table
        projects_table = self.query_one("#projects-table", DataTable)
        projects_table.add_columns("ID", "Name", "Owner")
        projects_table.cursor_type = "row"

    def load_users(self) -> None:
        """Load users into the sidebar."""
        users = self.db_manager.get_all_users()

        user_list = self.query_one("#user-list", ListView)
        user_list.clear()

        # Add "All Users" option
        user_list.append(ListItem(Label("All Users"), id="user-all"))

        for user in users:
            user_list.append(ListItem(Label(user), id=f"user-{user}"))

        self.log_message(f"Loaded {len(users)} users")

        # Also load for sessions tab
        session_user_list = self.query_one("#session-user-list", ListView)
        session_user_list.clear()
        for user in users:
            session_user_list.append(ListItem(Label(user), id=f"session-user-{user}"))

    def load_projects(self) -> None:
        """Load projects into the projects table."""
        projects = self.db_manager.get_all_projects()

        table = self.query_one("#projects-table", DataTable)
        table.clear()

        for pid, name, owner in projects:
            table.add_row(pid[:8] + "...", name, owner, key=pid)

        self.log_message(f"Loaded {len(projects)} projects")

    def load_memories(
        self,
        user_id: str | None = None,
        memory_type: str | None = None,
    ) -> None:
        """Load memories into the table."""
        table = self.query_one("#memory-table", DataTable)
        table.clear()

        if user_id:
            memories = self.db_manager.get_memories_for_user(
                user_id,
                memory_type=memory_type if memory_type != "all" else None,
            )
        else:
            # Load from all users
            users = self.db_manager.get_all_users()
            memories = []
            for uid in users:
                memories.extend(
                    self.db_manager.get_memories_for_user(
                        uid,
                        memory_type=memory_type if memory_type != "all" else None,
                    )
                )

        self.memories = memories

        for mem in memories:
            content = mem.get("content", "")
            if len(content) > 60:
                content = content[:60] + "..."

            updated = mem.get("updated_at", "")
            if updated:
                try:
                    if isinstance(updated, str):
                        updated = updated[:10]
                    elif isinstance(updated, datetime):
                        updated = updated.strftime("%Y-%m-%d")
                except Exception:
                    pass

            table.add_row(
                mem.get("id", "")[:8] + "...",
                content,
                mem.get("memory_type", "?"),
                (mem.get("project_id") or "-")[:12],
                str(updated),
                key=mem.get("id"),
            )

        self.log_message(f"Loaded {len(memories)} memories")

    def refresh_stats(self) -> None:
        """Refresh the statistics panel."""
        stats = self.db_manager.get_memory_stats()

        if "error" in stats:
            md = f"## Error\n\n{stats['error']}"
        else:
            by_type = stats.get("by_type", {})
            by_user = stats.get("by_user", {})

            md = f"""## Memory Statistics

**Total Memories:** {stats.get("total", 0)}

### By Type
| Type | Count |
|------|-------|
| Stable | {by_type.get("stable", 0)} |
| Active | {by_type.get("active", 0)} |
| Ephemeral | {by_type.get("ephemeral", 0)} |
| Unknown | {by_type.get("unknown", 0)} |

### By User
| User | Count |
|------|-------|
"""
            for user, count in sorted(by_user.items(), key=lambda x: -x[1])[:10]:
                md += f"| {user} | {count} |\n"

        content = self.query_one("#stats-content", Markdown)
        content.update(md)

    # Event handlers

    @on(ListView.Selected, "#user-list")
    def user_selected(self, event: ListView.Selected) -> None:
        """Handle user selection."""
        item_id = event.item.id or ""

        if item_id == "user-all":
            self.selected_user = None
            self.log_message("Selected: All Users")
        else:
            user_id = item_id.replace("user-", "")
            self.selected_user = user_id
            self.log_message(f"Selected user: {user_id}")

        # Get current type filter
        type_filter = self.query_one("#type-filter", Select).value

        # Load memories for selected user
        self.load_memories(
            user_id=self.selected_user,
            memory_type=type_filter if type_filter != "all" else None,
        )

    @on(ListView.Selected, "#session-user-list")
    def session_user_selected(self, event: ListView.Selected) -> None:
        """Handle user selection for sessions."""
        item_id = event.item.id or ""
        user_id = item_id.replace("session-user-", "")

        sessions = self.db_manager.get_sessions_for_user(user_id)

        table = self.query_one("#sessions-table", DataTable)
        table.clear()

        for sess in sessions:
            table.add_row(
                sess["id"][:8] + "...",
                sess["title"][:30] if sess["title"] else "Untitled",
                sess["started_at"].strftime("%Y-%m-%d") if sess["started_at"] else "",
                sess["last_activity"].strftime("%Y-%m-%d %H:%M") if sess["last_activity"] else "",
                "Yes" if sess["archived"] else "No",
                "Yes" if sess["has_summary"] else "No",
                key=sess["id"],
            )

        self.log_message(f"Loaded {len(sessions)} sessions for {user_id}")

    @on(Select.Changed, "#type-filter")
    def type_filter_changed(self, event: Select.Changed) -> None:
        """Handle type filter change."""
        self.load_memories(
            user_id=self.selected_user,
            memory_type=event.value if event.value != "all" else None,
        )

    @on(DataTable.RowSelected, "#memory-table")
    def memory_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle memory row selection."""
        if event.row_key:
            self.selected_memory_id = str(event.row_key.value)

    @on(Button.Pressed, "#btn-new")
    def new_memory_button(self) -> None:
        self.action_new_memory()

    @on(Button.Pressed, "#btn-edit")
    def edit_memory_button(self) -> None:
        self.action_edit_memory()

    @on(Button.Pressed, "#btn-delete")
    def delete_memory_button(self) -> None:
        self.action_delete_memory()

    @on(Button.Pressed, "#btn-view")
    def view_memory_button(self) -> None:
        """View selected memory details."""
        if not self.selected_memory_id:
            self.notify("No memory selected", severity="warning")
            return

        memory = self.db_manager.get_memory(self.selected_memory_id)
        if memory:
            self.push_screen(MemoryDetailScreen(memory))
        else:
            self.notify("Memory not found", severity="error")

    @on(Button.Pressed, "#btn-refresh")
    def refresh_button(self) -> None:
        self.action_refresh()

    @on(Button.Pressed, "#btn-search")
    def search_button(self) -> None:
        """Perform search."""
        query = self.query_one("#search-input", Input).value
        if not query.strip():
            self.notify("Enter a search query", severity="warning")
            return

        self.perform_search(query)

    @on(Button.Pressed, "#btn-clear-search")
    def clear_search_button(self) -> None:
        """Clear search and show all memories."""
        self.query_one("#search-input", Input).value = ""
        type_filter = self.query_one("#type-filter", Select).value
        self.load_memories(
            user_id=self.selected_user,
            memory_type=type_filter if type_filter != "all" else None,
        )

    @on(Input.Submitted, "#search-input")
    def search_submitted(self, event: Input.Submitted) -> None:
        """Handle search input submission."""
        if event.value.strip():
            self.perform_search(event.value)

    def perform_search(self, query: str) -> None:
        """Perform memory search."""
        self.log_message(f"Searching: {query}")

        results = self.db_manager.search_memories(
            query,
            user_id=self.selected_user,
        )

        # Update table with results
        table = self.query_one("#memory-table", DataTable)
        table.clear()

        for mem in results:
            content = mem.get("content", "")
            if len(content) > 60:
                content = content[:60] + "..."

            score = mem.get("score", 0)

            table.add_row(
                mem.get("id", "")[:8] + "...",
                content,
                mem.get("memory_type", "?"),
                f"{score:.3f}",  # Show score instead of project for search results
                mem.get("user_id", "")[:15],
                key=mem.get("id"),
            )

        self.memories = results
        self.log_message(f"Found {len(results)} results", "success")

    # Actions

    def action_refresh(self) -> None:
        """Refresh data."""
        self.load_users()
        self.load_projects()
        type_filter = self.query_one("#type-filter", Select).value
        self.load_memories(
            user_id=self.selected_user,
            memory_type=type_filter if type_filter != "all" else None,
        )
        self.refresh_stats()
        self.notify("Data refreshed")

    def action_new_memory(self) -> None:
        """Create a new memory."""
        if not self.db_manager.mem0:
            self.notify("Mem0 not connected", severity="error")
            return

        def on_result(result: dict | None) -> None:
            if result:
                success = self.db_manager.create_memory(
                    content=result["content"],
                    user_id=result["user_id"],
                    memory_type=result["memory_type"],
                    project_id=result["project_id"],
                    infer=False,  # Store directly without LLM inference
                )
                if success:
                    self.notify("Memory created", severity="information")
                    self.log_message("Memory created successfully", "success")
                    self.action_refresh()
                else:
                    self.notify("Failed to create memory", severity="error")
                    self.log_message("Failed to create memory", "error")

        self.push_screen(
            CreateMemoryScreen(self.db_manager, self.selected_user or ""),
            on_result,
        )

    def action_edit_memory(self) -> None:
        """Edit selected memory."""
        if not self.selected_memory_id:
            self.notify("No memory selected", severity="warning")
            return

        memory = self.db_manager.get_memory(self.selected_memory_id)
        if not memory:
            self.notify("Memory not found", severity="error")
            return

        def on_result(result: dict | None) -> None:
            if result:
                # Update content
                if result["content"] != memory.get("content"):
                    success = self.db_manager.update_memory(
                        result["id"],
                        result["content"],
                    )
                    if not success:
                        self.notify("Failed to update content", severity="error")
                        return

                # Update metadata if type changed
                if result["memory_type"] != memory.get("memory_type"):
                    payload = memory.get("payload", {}).copy()
                    payload["memory_type"] = result["memory_type"]
                    payload["updated_at"] = datetime.now(timezone.utc).isoformat()

                    success = self.db_manager.update_memory_metadata(
                        result["id"],
                        payload,
                    )
                    if not success:
                        self.notify("Failed to update type", severity="error")
                        return

                self.notify("Memory updated", severity="information")
                self.log_message("Memory updated successfully", "success")
                self.action_refresh()

        self.push_screen(EditMemoryScreen(memory), on_result)

    def action_delete_memory(self) -> None:
        """Delete selected memory."""
        if not self.selected_memory_id:
            self.notify("No memory selected", severity="warning")
            return

        # Find memory content for confirmation
        memory = next((m for m in self.memories if m.get("id") == self.selected_memory_id), None)
        content_preview = ""
        if memory:
            content = memory.get("content", "")
            content_preview = content[:100] + "..." if len(content) > 100 else content

        def on_confirm(confirmed: bool) -> None:
            if confirmed:
                success = self.db_manager.delete_memory(self.selected_memory_id)
                if success:
                    self.notify("Memory deleted", severity="information")
                    self.log_message("Memory deleted successfully", "success")
                    self.selected_memory_id = None
                    self.action_refresh()
                else:
                    self.notify("Failed to delete memory", severity="error")
                    self.log_message("Failed to delete memory", "error")

        self.push_screen(
            ConfirmDialog(
                "Delete Memory?",
                f"Are you sure you want to delete this memory?\n\n{content_preview}",
            ),
            on_confirm,
        )

    def action_focus_search(self) -> None:
        """Focus the search input."""
        self.query_one("#search-input", Input).focus()

    def action_show_help(self) -> None:
        """Show help information."""
        help_md = """# Memory Admin TUI Help

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Refresh data |
| `n` | Create new memory |
| `e` | Edit selected memory |
| `d` | Delete selected memory |
| `s` or `/` | Focus search |
| `F1` | Show this help |

## Navigation

- Use **Tab** to move between panels
- Use **Arrow keys** to navigate lists and tables
- Press **Enter** to select items

## Memory Types

- **Stable**: Core identity, preferences, relationships (slow decay)
- **Active**: Current projects, ongoing work (medium decay)
- **Ephemeral**: Temporary states, events (fast decay)

## Database Connections

- **Main DB**: PostgreSQL/SQLite for sessions, projects, messages
- **Mem0**: pgvector/Qdrant for vector-based memory storage
"""
        self.notify(help_md[:200] + "...", title="Help", severity="information")


# =============================================================================
# Entry Point
# =============================================================================


def main():
    """Run the Memory Admin TUI."""
    app = MemoryAdminApp()
    app.run()


if __name__ == "__main__":
    main()
