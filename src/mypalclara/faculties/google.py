"""
Google Faculty - Google Workspace and Calendar integration.

Uses the official google-api-python-client SDK for Sheets, Drive, Docs, and Calendar.
Requires per-user OAuth authentication.
"""

import asyncio
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import partial
from typing import Any, Optional

from mypalclara.faculties.base import Faculty
from mypalclara.models.state import FacultyResult

logger = logging.getLogger(__name__)

# Thread pool for sync SDK calls
_executor = ThreadPoolExecutor(max_workers=4)

# Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "")
CLARA_API_URL = os.getenv("CLARA_API_URL", "")

# API scopes
SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/calendar",
]


def is_configured() -> bool:
    """Check if Google OAuth is configured."""
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


class GoogleFaculty(Faculty):
    """Google Workspace and Calendar faculty using official SDK."""

    name = "google"
    description = "Google Sheets, Drive, Docs, and Calendar integration"

    available_actions = [
        # Connection
        "connect",
        "status",
        "disconnect",
        # Sheets
        "sheets_create",
        "sheets_read",
        "sheets_write",
        "sheets_append",
        "sheets_list",
        "sheets_get",
        "sheets_add_sheet",
        "sheets_delete_sheet",
        # Drive
        "drive_list",
        "drive_upload",
        "drive_download",
        "drive_create_folder",
        "drive_share",
        "drive_move",
        "drive_copy",
        "drive_rename",
        "drive_delete",
        "drive_get_file",
        "drive_search",
        # Docs
        "docs_create",
        "docs_read",
        "docs_write",
        "docs_insert",
        # Calendar
        "calendar_list_events",
        "calendar_get_event",
        "calendar_create_event",
        "calendar_update_event",
        "calendar_delete_event",
        "calendar_list_calendars",
        "calendar_quick_add",
    ]

    def __init__(self):
        self._credentials_cache: dict[str, Any] = {}

    async def _run_sync(self, func, *args, **kwargs):
        """Run a synchronous function in the thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, partial(func, *args, **kwargs))

    def _build_credentials(self, token: str, refresh_token: str | None = None) -> Any:
        """Build Google credentials from OAuth token."""
        from google.oauth2.credentials import Credentials

        return Credentials(
            token=token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            scopes=SCOPES,
        )

    def _build_service(self, service_name: str, version: str, credentials) -> Any:
        """Build a Google API service object."""
        from googleapiclient.discovery import build

        return build(service_name, version, credentials=credentials)

    async def _get_credentials(self, user_id: str) -> Any:
        """Get valid credentials for a user."""
        try:
            from mypalclara.oauth.google import get_valid_token, get_refresh_token

            token = await get_valid_token(user_id)
            if not token:
                return None

            refresh_token = await get_refresh_token(user_id)
            return self._build_credentials(token, refresh_token)
        except ImportError as e:
            logger.warning(f"[google] OAuth module import failed: {e}")
            return None

    async def _get_sheets_service(self, user_id: str):
        """Get Google Sheets service for user."""
        creds = await self._get_credentials(user_id)
        if not creds:
            raise ValueError("Google account not connected. Use 'connect google' first.")
        return await self._run_sync(self._build_service, "sheets", "v4", creds)

    async def _get_drive_service(self, user_id: str):
        """Get Google Drive service for user."""
        creds = await self._get_credentials(user_id)
        if not creds:
            raise ValueError("Google account not connected. Use 'connect google' first.")
        return await self._run_sync(self._build_service, "drive", "v3", creds)

    async def _get_docs_service(self, user_id: str):
        """Get Google Docs service for user."""
        creds = await self._get_credentials(user_id)
        if not creds:
            raise ValueError("Google account not connected. Use 'connect google' first.")
        return await self._run_sync(self._build_service, "docs", "v1", creds)

    async def _get_calendar_service(self, user_id: str):
        """Get Google Calendar service for user."""
        creds = await self._get_credentials(user_id)
        if not creds:
            raise ValueError("Google account not connected. Use 'connect google' first.")
        return await self._run_sync(self._build_service, "calendar", "v3", creds)

    async def execute(
        self,
        intent: str,
        constraints: Optional[list[str]] = None,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> FacultyResult:
        """Execute Google-related intent."""
        logger.info(f"[google] Intent: {intent} (user={user_id})")

        try:
            action, params = self._parse_intent(intent)
            # Inject actual user_id from execution context
            params["user_id"] = user_id or params.get("user_id", "default")
            params["channel_id"] = channel_id
            logger.info(f"[google] Action: {action} for user {params['user_id']}")

            # Route to action handler
            handler = getattr(self, f"_action_{action}", None)
            if handler:
                return await handler(params)
            else:
                return FacultyResult(
                    success=False,
                    summary=f"Unknown Google action: {action}",
                    error=f"Action '{action}' not recognized",
                )

        except Exception as e:
            logger.exception(f"[google] Error: {e}")
            return FacultyResult(
                success=False,
                summary=f"Google error: {str(e)}",
                error=str(e),
            )

    # ==========================================================================
    # Intent Parsing
    # ==========================================================================

    def _parse_intent(self, intent: str) -> tuple[str, dict]:
        """Parse natural language intent into action and parameters."""
        intent_lower = intent.lower()

        # Connection
        if any(phrase in intent_lower for phrase in ["connect google", "link google", "authenticate"]):
            return "connect", self._extract_params(intent)
        if any(phrase in intent_lower for phrase in ["google status", "is google connected"]):
            return "status", self._extract_params(intent)
        if any(phrase in intent_lower for phrase in ["disconnect google", "unlink google"]):
            return "disconnect", self._extract_params(intent)

        # Sheets
        if "create spreadsheet" in intent_lower or "new spreadsheet" in intent_lower:
            return "sheets_create", self._extract_params(intent)
        if "read spreadsheet" in intent_lower or "get spreadsheet data" in intent_lower:
            return "sheets_read", self._extract_params(intent)
        if "write spreadsheet" in intent_lower or "update spreadsheet" in intent_lower:
            return "sheets_write", self._extract_params(intent)
        if "append" in intent_lower and "spreadsheet" in intent_lower:
            return "sheets_append", self._extract_params(intent)
        if "list spreadsheet" in intent_lower or "my spreadsheets" in intent_lower:
            return "sheets_list", self._extract_params(intent)
        if "add sheet" in intent_lower or "new sheet" in intent_lower:
            return "sheets_add_sheet", self._extract_params(intent)
        if "delete sheet" in intent_lower or "remove sheet" in intent_lower:
            return "sheets_delete_sheet", self._extract_params(intent)

        # Drive
        if "search" in intent_lower and "drive" in intent_lower:
            return "drive_search", self._extract_params(intent)
        if "list files" in intent_lower or "list drive" in intent_lower or "my files" in intent_lower:
            return "drive_list", self._extract_params(intent)
        if "upload" in intent_lower and "drive" in intent_lower:
            return "drive_upload", self._extract_params(intent)
        if "download" in intent_lower and "drive" in intent_lower:
            return "drive_download", self._extract_params(intent)
        if "create folder" in intent_lower:
            return "drive_create_folder", self._extract_params(intent)
        if "share" in intent_lower and ("file" in intent_lower or "drive" in intent_lower):
            return "drive_share", self._extract_params(intent)
        if "move" in intent_lower and ("file" in intent_lower or "drive" in intent_lower):
            return "drive_move", self._extract_params(intent)
        if "copy" in intent_lower and ("file" in intent_lower or "drive" in intent_lower):
            return "drive_copy", self._extract_params(intent)
        if "rename" in intent_lower and ("file" in intent_lower or "drive" in intent_lower):
            return "drive_rename", self._extract_params(intent)
        if "delete" in intent_lower and ("drive" in intent_lower or "file" in intent_lower):
            return "drive_delete", self._extract_params(intent)
        if "file info" in intent_lower or "get file" in intent_lower:
            return "drive_get_file", self._extract_params(intent)

        # Docs
        if "create doc" in intent_lower or "new document" in intent_lower:
            return "docs_create", self._extract_params(intent)
        if "read doc" in intent_lower or "get document" in intent_lower:
            return "docs_read", self._extract_params(intent)
        if "write doc" in intent_lower or "append doc" in intent_lower:
            return "docs_write", self._extract_params(intent)
        if "insert" in intent_lower and "doc" in intent_lower:
            return "docs_insert", self._extract_params(intent)

        # Calendar - check these patterns before falling through to status
        if "quick add" in intent_lower:
            return "calendar_quick_add", self._extract_params(intent)
        # List events - many ways to ask for this
        if any(phrase in intent_lower for phrase in [
            "list event", "upcoming event", "my calendar", "calendar event",
            "get event", "show event", "what's on", "whats on", "events for",
            "events from", "events next", "events this", "schedule for",
            "my schedule", "check calendar", "check my calendar",
            "what event", "events do i have", "events i have", "do i have event",
        ]):
            return "calendar_list_events", self._extract_params(intent)
        if "create event" in intent_lower or "add to calendar" in intent_lower or "new event" in intent_lower:
            return "calendar_create_event", self._extract_params(intent)
        if "schedule" in intent_lower and "event" not in intent_lower:
            # "schedule a meeting" but not "schedule event" (already caught above)
            return "calendar_create_event", self._extract_params(intent)
        if "update event" in intent_lower or "modify event" in intent_lower or "change event" in intent_lower:
            return "calendar_update_event", self._extract_params(intent)
        if "delete event" in intent_lower or "cancel event" in intent_lower or "remove event" in intent_lower:
            return "calendar_delete_event", self._extract_params(intent)
        if "list calendar" in intent_lower or "my calendars" in intent_lower or "which calendar" in intent_lower:
            return "calendar_list_calendars", self._extract_params(intent)

        # Default
        return "status", self._extract_params(intent)

    def _extract_params(self, text: str) -> dict:
        """Extract all possible parameters from text."""
        import re

        params: dict[str, Any] = {}

        # Extract user_id (default if not found)
        params["user_id"] = "default"

        # Extract IDs
        match = re.search(r'\b([a-zA-Z0-9_-]{20,})\b', text)
        if match:
            params["id"] = match.group(1)
            params["spreadsheet_id"] = match.group(1)
            params["file_id"] = match.group(1)
            params["document_id"] = match.group(1)
            params["event_id"] = match.group(1)

        # Extract title/name
        match = re.search(r'(?:titled?|called?|named?)\s+["\']([^"\']+)["\']', text, re.IGNORECASE)
        if match:
            params["title"] = match.group(1)
            params["name"] = match.group(1)
        else:
            match = re.search(r'["\']([^"\']+)["\']', text)
            if match:
                params["title"] = match.group(1)
                params["name"] = match.group(1)

        # Extract A1 range
        match = re.search(r'\b([A-Z]+\d+(?::[A-Z]+\d+)?)\b', text)
        if match:
            params["range"] = match.group(1)

        # Extract values (JSON array)
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            try:
                params["values"] = json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        # Extract content
        match = re.search(r'```\s*(.*?)```', text, re.DOTALL)
        if match:
            params["content"] = match.group(1).strip()
        else:
            match = re.search(r'content[:\s]+["\'](.+?)["\']', text, re.DOTALL)
            if match:
                params["content"] = match.group(1)

        # Extract query
        match = re.search(r'(?:query|search|find)\s+["\']?([^"\']+)["\']?', text, re.IGNORECASE)
        if match:
            params["query"] = match.group(1)

        # Extract email
        match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        if match:
            params["email"] = match.group(0)

        # Extract filename
        match = re.search(r'["\']([^"\']+\.[a-zA-Z0-9]+)["\']', text)
        if match:
            params["filename"] = match.group(1)
        else:
            match = re.search(r'\b([\w\-]+\.[\w]+)\b', text)
            if match:
                params["filename"] = match.group(1)

        # Extract datetime (ISO format)
        match = re.search(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}', text)
        if match:
            params["start"] = match.group(0)

        # Extract location
        match = re.search(r'(?:at|location)\s+["\']([^"\']+)["\']', text, re.IGNORECASE)
        if match:
            params["location"] = match.group(1)

        # Extract calendar name (e.g., "from the Family calendar", "on my Work calendar", "the Personal calendar")
        # Require a preposition or "the/my" before the calendar name
        match = re.search(r'(?:from|on|in)\s+(?:the\s+)?(?:my\s+)?["\']?(\w+)["\']?\s+calendar', text, re.IGNORECASE)
        if not match:
            # Try "the X calendar" or "my X calendar" without preposition
            match = re.search(r'(?:the|my)\s+["\']?(\w+)["\']?\s+calendar', text, re.IGNORECASE)
        if match and match.group(1).lower() not in ["my", "the", "a", "google"]:
            params["calendar_name"] = match.group(1)

        # Extract summary for events
        match = re.search(r'(?:titled?|called?|for|about)\s+["\']([^"\']+)["\']', text, re.IGNORECASE)
        if match:
            params["summary"] = match.group(1)

        # Check for shared files inclusion
        if any(phrase in text.lower() for phrase in ["include shared", "shared files", "including shared", "with shared"]):
            params["include_shared"] = True

        return params

    # ==========================================================================
    # Connection Management
    # ==========================================================================

    async def _action_connect(self, params: dict) -> FacultyResult:
        """Generate OAuth URL to connect Google account."""
        if not is_configured():
            return FacultyResult(
                success=False,
                summary="Google OAuth not configured",
                error="GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET not set",
            )

        user_id = params.get("user_id", "default")

        if CLARA_API_URL:
            auth_url = f"{CLARA_API_URL}/oauth/google/start/{user_id}"
        else:
            scope = " ".join(SCOPES)
            auth_url = (
                f"https://accounts.google.com/o/oauth2/v2/auth"
                f"?client_id={GOOGLE_CLIENT_ID}"
                f"&redirect_uri={GOOGLE_REDIRECT_URI}"
                f"&response_type=code"
                f"&scope={scope}"
                f"&state={user_id}"
                f"&access_type=offline"
                f"&prompt=consent"
            )

        return FacultyResult(
            success=True,
            summary=f"Click here to connect your Google account:\n{auth_url}",
            data={"auth_url": auth_url},
        )

    async def _action_status(self, params: dict) -> FacultyResult:
        """Check Google connection status."""
        user_id = params.get("user_id", "default")

        if not is_configured():
            return FacultyResult(
                success=True,
                summary="Google OAuth not configured on this instance",
                data={"configured": False, "connected": False},
            )

        creds = await self._get_credentials(user_id)
        connected = creds is not None

        return FacultyResult(
            success=True,
            summary=f"Google account: {'Connected' if connected else 'Not connected'}",
            data={"configured": True, "connected": connected},
        )

    async def _action_disconnect(self, params: dict) -> FacultyResult:
        """Disconnect Google account."""
        user_id = params.get("user_id", "default")

        try:
            from mypalclara.oauth.google import revoke_token

            result = await revoke_token(user_id)
            if result:
                return FacultyResult(
                    success=True,
                    summary="Google account disconnected",
                    data={"disconnected": True},
                )
            else:
                return FacultyResult(
                    success=False,
                    summary="Failed to disconnect Google account",
                    error="Revoke failed",
                )
        except ImportError as e:
            return FacultyResult(
                success=False,
                summary="Google OAuth module not available",
                error=str(e),
            )

    # ==========================================================================
    # Google Sheets Operations
    # ==========================================================================

    async def _action_sheets_create(self, params: dict) -> FacultyResult:
        """Create a new Google spreadsheet."""
        user_id = params.get("user_id", "default")
        title = params.get("title", "New Spreadsheet")

        service = await self._get_sheets_service(user_id)

        def create():
            return service.spreadsheets().create(body={"properties": {"title": title}}).execute()

        result = await self._run_sync(create)

        return FacultyResult(
            success=True,
            summary=f"Created spreadsheet '{title}'\nID: {result.get('spreadsheetId')}\nURL: {result.get('spreadsheetUrl')}",
            data=result,
        )

    async def _action_sheets_read(self, params: dict) -> FacultyResult:
        """Read data from a spreadsheet."""
        user_id = params.get("user_id", "default")
        spreadsheet_id = params.get("spreadsheet_id", params.get("id", ""))
        range_str = params.get("range", "A1:Z100")

        if not spreadsheet_id:
            return FacultyResult(success=False, summary="No spreadsheet ID provided", error="Missing spreadsheet_id")

        service = await self._get_sheets_service(user_id)

        def read():
            return service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_str).execute()

        result = await self._run_sync(read)
        values = result.get("values", [])
        formatted = "\n".join(["\t".join(str(cell) for cell in row) for row in values[:20]])

        return FacultyResult(
            success=True,
            summary=f"Read {len(values)} rows from {range_str}:\n```\n{formatted}\n```",
            data={"values": values, "range": range_str},
        )

    async def _action_sheets_write(self, params: dict) -> FacultyResult:
        """Write data to a spreadsheet."""
        user_id = params.get("user_id", "default")
        spreadsheet_id = params.get("spreadsheet_id", params.get("id", ""))
        range_str = params.get("range", "A1")
        values = params.get("values", [])

        if not spreadsheet_id:
            return FacultyResult(success=False, summary="No spreadsheet ID provided", error="Missing spreadsheet_id")

        service = await self._get_sheets_service(user_id)

        def write():
            return (
                service.spreadsheets()
                .values()
                .update(
                    spreadsheetId=spreadsheet_id,
                    range=range_str,
                    valueInputOption="USER_ENTERED",
                    body={"values": values},
                )
                .execute()
            )

        result = await self._run_sync(write)

        return FacultyResult(
            success=True,
            summary=f"Updated {result.get('updatedCells', 0)} cells in {range_str}",
            data=result,
        )

    async def _action_sheets_append(self, params: dict) -> FacultyResult:
        """Append rows to a spreadsheet."""
        user_id = params.get("user_id", "default")
        spreadsheet_id = params.get("spreadsheet_id", params.get("id", ""))
        range_str = params.get("range", "A1")
        values = params.get("values", [])

        if not spreadsheet_id:
            return FacultyResult(success=False, summary="No spreadsheet ID provided", error="Missing spreadsheet_id")

        service = await self._get_sheets_service(user_id)

        def append():
            return (
                service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=spreadsheet_id,
                    range=range_str,
                    valueInputOption="USER_ENTERED",
                    insertDataOption="INSERT_ROWS",
                    body={"values": values},
                )
                .execute()
            )

        result = await self._run_sync(append)

        return FacultyResult(
            success=True,
            summary=f"Appended {len(values)} rows",
            data=result,
        )

    async def _action_sheets_list(self, params: dict) -> FacultyResult:
        """List user's spreadsheets."""
        user_id = params.get("user_id", "default")

        service = await self._get_drive_service(user_id)

        def list_sheets():
            return (
                service.files()
                .list(
                    q="mimeType='application/vnd.google-apps.spreadsheet'",
                    fields="files(id,name,modifiedTime)",
                    pageSize=50,
                )
                .execute()
            )

        result = await self._run_sync(list_sheets)
        files = result.get("files", [])
        formatted = "\n".join([f"- {f['name']} (ID: {f['id']})" for f in files[:20]])

        return FacultyResult(
            success=True,
            summary=f"Found {len(files)} spreadsheets:\n{formatted}",
            data={"spreadsheets": files},
        )

    async def _action_sheets_get(self, params: dict) -> FacultyResult:
        """Get spreadsheet metadata."""
        user_id = params.get("user_id", "default")
        spreadsheet_id = params.get("spreadsheet_id", params.get("id", ""))

        if not spreadsheet_id:
            return FacultyResult(success=False, summary="No spreadsheet ID provided", error="Missing spreadsheet_id")

        service = await self._get_sheets_service(user_id)

        def get():
            return service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()

        result = await self._run_sync(get)
        sheets = result.get("sheets", [])
        sheet_names = [s.get("properties", {}).get("title", "Unknown") for s in sheets]

        return FacultyResult(
            success=True,
            summary=f"**{result.get('properties', {}).get('title')}**\nSheets: {', '.join(sheet_names)}",
            data=result,
        )

    async def _action_sheets_add_sheet(self, params: dict) -> FacultyResult:
        """Add a new sheet to a spreadsheet."""
        user_id = params.get("user_id", "default")
        spreadsheet_id = params.get("spreadsheet_id", params.get("id", ""))
        title = params.get("title", "New Sheet")

        if not spreadsheet_id:
            return FacultyResult(success=False, summary="No spreadsheet ID provided", error="Missing spreadsheet_id")

        service = await self._get_sheets_service(user_id)

        def add_sheet():
            return (
                service.spreadsheets()
                .batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
                )
                .execute()
            )

        result = await self._run_sync(add_sheet)

        return FacultyResult(
            success=True,
            summary=f"Added sheet '{title}'",
            data=result,
        )

    async def _action_sheets_delete_sheet(self, params: dict) -> FacultyResult:
        """Delete a sheet from a spreadsheet."""
        user_id = params.get("user_id", "default")
        spreadsheet_id = params.get("spreadsheet_id", params.get("id", ""))
        sheet_id = params.get("sheet_id", 0)

        if not spreadsheet_id:
            return FacultyResult(success=False, summary="No spreadsheet ID provided", error="Missing spreadsheet_id")

        service = await self._get_sheets_service(user_id)

        def delete_sheet():
            return (
                service.spreadsheets()
                .batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={"requests": [{"deleteSheet": {"sheetId": int(sheet_id)}}]},
                )
                .execute()
            )

        result = await self._run_sync(delete_sheet)

        return FacultyResult(
            success=True,
            summary=f"Deleted sheet {sheet_id}",
            data=result,
        )

    # ==========================================================================
    # Google Drive Operations
    # ==========================================================================

    async def _action_drive_list(self, params: dict) -> FacultyResult:
        """List files in Google Drive."""
        user_id = params.get("user_id", "default")
        query = params.get("query", "")
        page_size = params.get("page_size", 30)
        include_shared = params.get("include_shared", False)

        service = await self._get_drive_service(user_id)

        def list_files():
            # Build query - by default only show files owned by user (not shared with them)
            q_parts = []
            if query:
                q_parts.append(f"name contains '{query}'")
            if not include_shared:
                q_parts.append("'me' in owners")
            q = " and ".join(q_parts) if q_parts else None

            return (
                service.files()
                .list(
                    q=q,
                    pageSize=page_size,
                    fields="files(id,name,mimeType,size,modifiedTime,owners)",
                )
                .execute()
            )

        result = await self._run_sync(list_files)
        files = result.get("files", [])

        formatted = []
        for f in files[:25]:
            # Show ownership indicator
            owners = f.get("owners", [])
            is_mine = any(o.get("me", False) for o in owners)
            owner_tag = "" if is_mine else " [shared]"
            formatted.append(f"- {f['name']}{owner_tag}")

        ownership_note = "" if not include_shared else " (including shared)"
        return FacultyResult(
            success=True,
            summary=f"Found {len(files)} files{ownership_note}:\n" + "\n".join(formatted),
            data={"files": files},
        )

    async def _action_drive_search(self, params: dict) -> FacultyResult:
        """Search files in Google Drive."""
        user_id = params.get("user_id", "default")
        query = params.get("query", "")
        include_shared = params.get("include_shared", False)

        if not query:
            return FacultyResult(success=False, summary="No search query provided", error="Missing query")

        service = await self._get_drive_service(user_id)

        def search():
            # Build query - search content, optionally limit to owned files
            q = f"fullText contains '{query}'"
            if not include_shared:
                q += " and 'me' in owners"

            return (
                service.files()
                .list(
                    q=q,
                    pageSize=25,
                    fields="files(id,name,mimeType,modifiedTime,webViewLink,owners)",
                )
                .execute()
            )

        result = await self._run_sync(search)
        files = result.get("files", [])

        formatted = []
        for f in files[:20]:
            owners = f.get("owners", [])
            is_mine = any(o.get("me", False) for o in owners)
            owner_tag = "" if is_mine else " [shared]"
            link = f.get("webViewLink", "")
            if link:
                formatted.append(f"- [{f['name']}]({link}){owner_tag}")
            else:
                formatted.append(f"- {f['name']}{owner_tag}")

        ownership_note = "" if not include_shared else " (including shared)"
        return FacultyResult(
            success=True,
            summary=f"Found {len(files)} files matching '{query}'{ownership_note}:\n" + "\n".join(formatted),
            data={"files": files},
        )

    async def _action_drive_upload(self, params: dict) -> FacultyResult:
        """Upload a file to Google Drive."""
        user_id = params.get("user_id", "default")
        filename = params.get("filename", "file.txt")
        content = params.get("content", "")
        folder_id = params.get("folder_id")

        from googleapiclient.http import MediaInMemoryUpload

        service = await self._get_drive_service(user_id)

        metadata: dict[str, Any] = {"name": filename}
        if folder_id:
            metadata["parents"] = [folder_id]

        def upload():
            media = MediaInMemoryUpload(content.encode("utf-8"), mimetype="text/plain")
            return service.files().create(body=metadata, media_body=media, fields="id,name,webViewLink").execute()

        result = await self._run_sync(upload)

        return FacultyResult(
            success=True,
            summary=f"Uploaded '{filename}'\nID: {result.get('id')}\nLink: {result.get('webViewLink', 'N/A')}",
            data=result,
        )

    async def _action_drive_download(self, params: dict) -> FacultyResult:
        """Download a file from Google Drive."""
        user_id = params.get("user_id", "default")
        file_id = params.get("file_id", params.get("id", ""))

        if not file_id:
            return FacultyResult(success=False, summary="No file ID provided", error="Missing file_id")

        service = await self._get_drive_service(user_id)

        def download():
            return service.files().get_media(fileId=file_id).execute()

        content = await self._run_sync(download)

        # Handle bytes vs string
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")

        return FacultyResult(
            success=True,
            summary=f"Downloaded file ({len(content)} bytes):\n```\n{content[:1000]}\n```",
            data={"content": content, "file_id": file_id},
        )

    async def _action_drive_create_folder(self, params: dict) -> FacultyResult:
        """Create a folder in Google Drive."""
        user_id = params.get("user_id", "default")
        name = params.get("name", params.get("title", "New Folder"))
        parent_id = params.get("parent_id")

        service = await self._get_drive_service(user_id)

        metadata: dict[str, Any] = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            metadata["parents"] = [parent_id]

        def create():
            return service.files().create(body=metadata, fields="id,name,webViewLink").execute()

        result = await self._run_sync(create)

        return FacultyResult(
            success=True,
            summary=f"Created folder '{name}'\nID: {result.get('id')}",
            data=result,
        )

    async def _action_drive_share(self, params: dict) -> FacultyResult:
        """Share a file with someone."""
        user_id = params.get("user_id", "default")
        file_id = params.get("file_id", params.get("id", ""))
        email = params.get("email", "")
        role = params.get("role", "reader")

        if not file_id or not email:
            return FacultyResult(success=False, summary="file_id and email required", error="Missing parameters")

        service = await self._get_drive_service(user_id)

        def share():
            return (
                service.permissions()
                .create(
                    fileId=file_id,
                    body={"type": "user", "role": role, "emailAddress": email},
                    sendNotificationEmail=True,
                )
                .execute()
            )

        result = await self._run_sync(share)

        return FacultyResult(
            success=True,
            summary=f"Shared file with {email} as {role}",
            data=result,
        )

    async def _action_drive_move(self, params: dict) -> FacultyResult:
        """Move a file to a different folder."""
        user_id = params.get("user_id", "default")
        file_id = params.get("file_id", params.get("id", ""))
        folder_id = params.get("folder_id", "")

        if not file_id or not folder_id:
            return FacultyResult(success=False, summary="file_id and folder_id required", error="Missing parameters")

        service = await self._get_drive_service(user_id)

        def move():
            # Get current parents
            file = service.files().get(fileId=file_id, fields="parents").execute()
            previous_parents = ",".join(file.get("parents", []))
            # Move file
            return (
                service.files()
                .update(fileId=file_id, addParents=folder_id, removeParents=previous_parents, fields="id,name,parents")
                .execute()
            )

        result = await self._run_sync(move)

        return FacultyResult(
            success=True,
            summary=f"Moved file to folder {folder_id}",
            data=result,
        )

    async def _action_drive_copy(self, params: dict) -> FacultyResult:
        """Copy a file."""
        user_id = params.get("user_id", "default")
        file_id = params.get("file_id", params.get("id", ""))
        new_name = params.get("name", params.get("title"))

        if not file_id:
            return FacultyResult(success=False, summary="No file ID provided", error="Missing file_id")

        service = await self._get_drive_service(user_id)

        def copy():
            body = {"name": new_name} if new_name else {}
            return service.files().copy(fileId=file_id, body=body, fields="id,name,webViewLink").execute()

        result = await self._run_sync(copy)

        return FacultyResult(
            success=True,
            summary=f"Copied file as '{result.get('name')}'\nID: {result.get('id')}",
            data=result,
        )

    async def _action_drive_rename(self, params: dict) -> FacultyResult:
        """Rename a file."""
        user_id = params.get("user_id", "default")
        file_id = params.get("file_id", params.get("id", ""))
        new_name = params.get("name", params.get("title", ""))

        if not file_id or not new_name:
            return FacultyResult(success=False, summary="file_id and new name required", error="Missing parameters")

        service = await self._get_drive_service(user_id)

        def rename():
            return service.files().update(fileId=file_id, body={"name": new_name}, fields="id,name").execute()

        result = await self._run_sync(rename)

        return FacultyResult(
            success=True,
            summary=f"Renamed file to '{new_name}'",
            data=result,
        )

    async def _action_drive_delete(self, params: dict) -> FacultyResult:
        """Delete a file from Google Drive."""
        user_id = params.get("user_id", "default")
        file_id = params.get("file_id", params.get("id", ""))

        if not file_id:
            return FacultyResult(success=False, summary="No file ID provided", error="Missing file_id")

        service = await self._get_drive_service(user_id)

        def delete():
            service.files().delete(fileId=file_id).execute()
            return {"deleted": True}

        await self._run_sync(delete)

        return FacultyResult(
            success=True,
            summary=f"Deleted file {file_id}",
            data={"file_id": file_id, "deleted": True},
        )

    async def _action_drive_get_file(self, params: dict) -> FacultyResult:
        """Get file metadata."""
        user_id = params.get("user_id", "default")
        file_id = params.get("file_id", params.get("id", ""))

        if not file_id:
            return FacultyResult(success=False, summary="No file ID provided", error="Missing file_id")

        service = await self._get_drive_service(user_id)

        def get_file():
            return (
                service.files()
                .get(fileId=file_id, fields="id,name,mimeType,size,modifiedTime,webViewLink,parents")
                .execute()
            )

        result = await self._run_sync(get_file)

        return FacultyResult(
            success=True,
            summary=f"**{result.get('name')}**\nType: {result.get('mimeType')}\nSize: {result.get('size', 'N/A')} bytes\nLink: {result.get('webViewLink', 'N/A')}",
            data=result,
        )

    # ==========================================================================
    # Google Docs Operations
    # ==========================================================================

    async def _action_docs_create(self, params: dict) -> FacultyResult:
        """Create a new Google Doc."""
        user_id = params.get("user_id", "default")
        title = params.get("title", "New Document")

        service = await self._get_docs_service(user_id)

        def create():
            return service.documents().create(body={"title": title}).execute()

        result = await self._run_sync(create)

        return FacultyResult(
            success=True,
            summary=f"Created document '{title}'\nID: {result.get('documentId')}",
            data=result,
        )

    async def _action_docs_read(self, params: dict) -> FacultyResult:
        """Read a Google Doc."""
        user_id = params.get("user_id", "default")
        document_id = params.get("document_id", params.get("id", ""))

        if not document_id:
            return FacultyResult(success=False, summary="No document ID provided", error="Missing document_id")

        service = await self._get_docs_service(user_id)

        def read():
            return service.documents().get(documentId=document_id).execute()

        result = await self._run_sync(read)

        # Extract text content
        content_parts = []
        for element in result.get("body", {}).get("content", []):
            if "paragraph" in element:
                for text_run in element["paragraph"].get("elements", []):
                    if "textRun" in text_run:
                        content_parts.append(text_run["textRun"].get("content", ""))

        content = "".join(content_parts)

        return FacultyResult(
            success=True,
            summary=f"**{result.get('title')}**\n\n{content[:2000]}",
            data={"title": result.get("title"), "content": content, "documentId": document_id},
        )

    async def _action_docs_write(self, params: dict) -> FacultyResult:
        """Append text to a Google Doc."""
        user_id = params.get("user_id", "default")
        document_id = params.get("document_id", params.get("id", ""))
        content = params.get("content", "")

        if not document_id:
            return FacultyResult(success=False, summary="No document ID provided", error="Missing document_id")

        service = await self._get_docs_service(user_id)

        # First get the document to find the end index
        def get_doc():
            return service.documents().get(documentId=document_id).execute()

        doc = await self._run_sync(get_doc)
        end_index = doc.get("body", {}).get("content", [{}])[-1].get("endIndex", 1) - 1

        def write():
            return (
                service.documents()
                .batchUpdate(
                    documentId=document_id,
                    body={"requests": [{"insertText": {"location": {"index": end_index}, "text": content}}]},
                )
                .execute()
            )

        result = await self._run_sync(write)

        return FacultyResult(
            success=True,
            summary=f"Appended {len(content)} characters to document",
            data=result,
        )

    async def _action_docs_insert(self, params: dict) -> FacultyResult:
        """Insert text at a specific index in a Google Doc."""
        user_id = params.get("user_id", "default")
        document_id = params.get("document_id", params.get("id", ""))
        content = params.get("content", "")
        index = params.get("index", 1)

        if not document_id:
            return FacultyResult(success=False, summary="No document ID provided", error="Missing document_id")

        service = await self._get_docs_service(user_id)

        def insert():
            return (
                service.documents()
                .batchUpdate(
                    documentId=document_id,
                    body={"requests": [{"insertText": {"location": {"index": int(index)}, "text": content}}]},
                )
                .execute()
            )

        result = await self._run_sync(insert)

        return FacultyResult(
            success=True,
            summary=f"Inserted {len(content)} characters at index {index}",
            data=result,
        )

    # ==========================================================================
    # Google Calendar Operations
    # ==========================================================================

    async def _action_calendar_list_events(self, params: dict) -> FacultyResult:
        """List upcoming calendar events."""
        user_id = params.get("user_id", "default")
        calendar_id = params.get("calendar_id", "primary")
        calendar_name = params.get("calendar_name")  # e.g., "Family", "Work"
        max_results = params.get("max_results", 50)

        service = await self._get_calendar_service(user_id)
        time_min = datetime.now(timezone.utc).isoformat()

        # If a calendar name was specified, look it up
        if calendar_name and calendar_id == "primary":
            def get_calendars():
                return service.calendarList().list().execute()

            cal_result = await self._run_sync(get_calendars)
            calendars = cal_result.get("items", [])

            # Find calendar by name (case-insensitive)
            for cal in calendars:
                if calendar_name.lower() in cal.get("summary", "").lower():
                    calendar_id = cal.get("id")
                    logger.info(f"[google] Found calendar '{cal.get('summary')}' -> {calendar_id}")
                    break
            else:
                # List available calendars if not found
                available = [c.get("summary") for c in calendars]
                return FacultyResult(
                    success=False,
                    summary=f"Calendar '{calendar_name}' not found. Available calendars: {', '.join(available)}",
                    error="Calendar not found",
                    data={"available_calendars": available},
                )

        def list_events():
            return (
                service.events()
                .list(
                    calendarId=calendar_id,
                    maxResults=max_results,
                    orderBy="startTime",
                    singleEvents=True,
                    timeMin=time_min,
                )
                .execute()
            )

        result = await self._run_sync(list_events)
        events = result.get("items", [])

        formatted = []
        for event in events[:25]:  # Show up to 25 events
            start = event.get("start", {})
            start_time = start.get("dateTime", start.get("date", "Unknown"))
            # Format datetime more readably
            if "T" in str(start_time):
                try:
                    dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                    start_time = dt.strftime("%a %b %d at %I:%M %p")
                except (ValueError, AttributeError):
                    pass
            formatted.append(f"- **{event.get('summary', '(No title)')}** - {start_time}")

        calendar_label = f" from {calendar_name} calendar" if calendar_name else ""
        return FacultyResult(
            success=True,
            summary=f"Found {len(events)} events{calendar_label}:\n" + "\n".join(formatted) if formatted else "No upcoming events",
            data={"events": events, "calendar_id": calendar_id},
        )

    async def _action_calendar_get_event(self, params: dict) -> FacultyResult:
        """Get details of a specific event."""
        user_id = params.get("user_id", "default")
        event_id = params.get("event_id", params.get("id", ""))
        calendar_id = params.get("calendar_id", "primary")

        if not event_id:
            return FacultyResult(success=False, summary="No event ID provided", error="Missing event_id")

        service = await self._get_calendar_service(user_id)

        def get_event():
            return service.events().get(calendarId=calendar_id, eventId=event_id).execute()

        result = await self._run_sync(get_event)

        return FacultyResult(
            success=True,
            summary=json.dumps(result, indent=2),
            data=result,
        )

    async def _action_calendar_create_event(self, params: dict) -> FacultyResult:
        """Create a new calendar event."""
        user_id = params.get("user_id", "default")
        calendar_id = params.get("calendar_id", "primary")
        summary = params.get("summary", params.get("title", "New Event"))
        start = params.get("start", "")
        end = params.get("end", "")
        description = params.get("description")
        location = params.get("location")

        if not start or not end:
            return FacultyResult(success=False, summary="start and end times required", error="Missing start/end")

        service = await self._get_calendar_service(user_id)

        event_body: dict[str, Any] = {"summary": summary}

        # Handle start/end times
        if "T" in start:
            event_body["start"] = {"dateTime": start, "timeZone": "UTC"}
            event_body["end"] = {"dateTime": end, "timeZone": "UTC"}
        else:
            event_body["start"] = {"date": start}
            event_body["end"] = {"date": end}

        if description:
            event_body["description"] = description
        if location:
            event_body["location"] = location

        def create():
            return service.events().insert(calendarId=calendar_id, body=event_body).execute()

        result = await self._run_sync(create)

        return FacultyResult(
            success=True,
            summary=f"Created event '{summary}'\nID: {result.get('id')}\nLink: {result.get('htmlLink')}",
            data=result,
        )

    async def _action_calendar_update_event(self, params: dict) -> FacultyResult:
        """Update an existing calendar event."""
        user_id = params.get("user_id", "default")
        event_id = params.get("event_id", params.get("id", ""))
        calendar_id = params.get("calendar_id", "primary")

        if not event_id:
            return FacultyResult(success=False, summary="No event ID provided", error="Missing event_id")

        service = await self._get_calendar_service(user_id)

        # Get existing event
        def get_event():
            return service.events().get(calendarId=calendar_id, eventId=event_id).execute()

        existing = await self._run_sync(get_event)

        # Apply updates
        for key in ["summary", "description", "location"]:
            if params.get(key) is not None:
                existing[key] = params[key]

        if params.get("start"):
            start = params["start"]
            existing["start"] = {"dateTime": start, "timeZone": "UTC"} if "T" in start else {"date": start}

        if params.get("end"):
            end = params["end"]
            existing["end"] = {"dateTime": end, "timeZone": "UTC"} if "T" in end else {"date": end}

        def update():
            return service.events().update(calendarId=calendar_id, eventId=event_id, body=existing).execute()

        result = await self._run_sync(update)

        return FacultyResult(
            success=True,
            summary=f"Updated event '{result.get('summary')}'",
            data=result,
        )

    async def _action_calendar_delete_event(self, params: dict) -> FacultyResult:
        """Delete a calendar event."""
        user_id = params.get("user_id", "default")
        event_id = params.get("event_id", params.get("id", ""))
        calendar_id = params.get("calendar_id", "primary")

        if not event_id:
            return FacultyResult(success=False, summary="No event ID provided", error="Missing event_id")

        service = await self._get_calendar_service(user_id)

        def delete():
            service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            return {"deleted": True}

        await self._run_sync(delete)

        return FacultyResult(
            success=True,
            summary=f"Deleted event {event_id}",
            data={"event_id": event_id, "deleted": True},
        )

    async def _action_calendar_list_calendars(self, params: dict) -> FacultyResult:
        """List available calendars."""
        user_id = params.get("user_id", "default")

        service = await self._get_calendar_service(user_id)

        def list_calendars():
            return service.calendarList().list().execute()

        result = await self._run_sync(list_calendars)
        calendars = result.get("items", [])

        formatted = []
        for cal in calendars:
            primary = " (primary)" if cal.get("primary") else ""
            formatted.append(f"- **{cal.get('summary')}**{primary}\n  ID: {cal.get('id')}")

        return FacultyResult(
            success=True,
            summary=f"Available calendars:\n" + "\n".join(formatted),
            data={"calendars": calendars},
        )

    async def _action_calendar_quick_add(self, params: dict) -> FacultyResult:
        """Quick add an event using natural language."""
        user_id = params.get("user_id", "default")
        calendar_id = params.get("calendar_id", "primary")
        text = params.get("text", params.get("summary", ""))

        if not text:
            return FacultyResult(success=False, summary="No event text provided", error="Missing text")

        service = await self._get_calendar_service(user_id)

        def quick_add():
            return service.events().quickAdd(calendarId=calendar_id, text=text).execute()

        result = await self._run_sync(quick_add)

        return FacultyResult(
            success=True,
            summary=f"Created event '{result.get('summary')}'\nID: {result.get('id')}\nLink: {result.get('htmlLink')}",
            data=result,
        )
