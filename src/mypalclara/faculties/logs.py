"""
Logs Faculty - System logs access.

Provides tools for searching and retrieving system logs
from PostgreSQL for debugging and monitoring.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Optional

from mypalclara.faculties.base import Faculty
from mypalclara.models.state import FacultyResult

logger = logging.getLogger(__name__)

# Database session factory (set during initialization)
_session_factory = None


def set_session_factory(factory):
    """Set the database session factory."""
    global _session_factory
    _session_factory = factory


class LogsFaculty(Faculty):
    """System logs faculty."""

    name = "logs"
    description = "Search and retrieve system logs for debugging and monitoring"

    available_actions = [
        "search",
        "get_recent",
        "get_errors",
        "get_by_logger",
    ]

    async def execute(
        self,
        intent: str,
        constraints: Optional[list[str]] = None,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> FacultyResult:
        """Execute logs-related intent."""
        logger.info(f"[logs] Intent: {intent}")

        if _session_factory is None:
            # Try to get session factory
            try:
                from db import SessionLocal
                set_session_factory(SessionLocal)
            except ImportError:
                return FacultyResult(
                    success=False,
                    summary="Database not available for log access",
                    error="No database connection",
                )

        try:
            action, params = self._parse_intent(intent)
            logger.info(f"[logs] Action: {action}")

            if action == "search":
                result = await self._search(params)
            elif action == "get_recent":
                result = await self._get_recent(params)
            elif action == "get_errors":
                result = await self._get_errors(params)
            elif action == "get_by_logger":
                result = await self._get_by_logger(params)
            else:
                return FacultyResult(
                    success=False,
                    summary=f"Unknown logs action: {action}",
                    error=f"Action '{action}' not recognized",
                )

            return result

        except Exception as e:
            logger.exception(f"[logs] Error: {e}")
            return FacultyResult(
                success=False,
                summary=f"Logs error: {str(e)}",
                error=str(e),
            )

    def _parse_intent(self, intent: str) -> tuple[str, dict]:
        """Parse natural language intent into action and parameters."""
        intent_lower = intent.lower()

        # Search patterns
        if any(phrase in intent_lower for phrase in ["search logs", "find logs", "log search"]):
            query = self._extract_query(intent)
            level = self._extract_level(intent)
            return "search", {"query": query, "level": level}

        # Error logs
        if any(phrase in intent_lower for phrase in ["error", "exception", "fail"]):
            hours = self._extract_hours(intent)
            return "get_errors", {"hours": hours}

        # By logger
        if any(phrase in intent_lower for phrase in ["logger", "from module", "from service"]):
            logger_name = self._extract_logger(intent)
            return "get_by_logger", {"logger_name": logger_name}

        # Default to get recent
        limit = self._extract_limit(intent)
        return "get_recent", {"limit": limit}

    def _extract_query(self, text: str) -> str:
        """Extract search query from text."""
        import re
        match = re.search(r'["\']([^"\']+)["\']', text)
        if match:
            return match.group(1)

        for phrase in ["search for", "find", "containing"]:
            if phrase in text.lower():
                idx = text.lower().find(phrase) + len(phrase)
                return text[idx:].strip().split()[0] if text[idx:].strip() else ""

        return ""

    def _extract_level(self, text: str) -> str:
        """Extract log level from text."""
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in levels:
            if level.lower() in text.lower():
                return level
        return ""

    def _extract_hours(self, text: str) -> int:
        """Extract hours from text."""
        import re
        match = re.search(r'(\d+)\s*(?:hour|hr)', text, re.IGNORECASE)
        if match:
            return int(match.group(1))

        match = re.search(r'(\d+)\s*(?:day)', text, re.IGNORECASE)
        if match:
            return int(match.group(1)) * 24

        return 24

    def _extract_logger(self, text: str) -> str:
        """Extract logger name from text."""
        import re
        match = re.search(r'(?:logger|module|service)[:\s]+["\']?(\w+)["\']?', text, re.IGNORECASE)
        return match.group(1) if match else ""

    def _extract_limit(self, text: str) -> int:
        """Extract limit from text."""
        import re
        match = re.search(r'(\d+)\s*(?:log|entr)', text, re.IGNORECASE)
        if match:
            return min(int(match.group(1)), 100)
        return 30

    async def _search(self, params: dict) -> FacultyResult:
        """Search system logs by keyword, logger, or level."""
        try:
            from db.models import LogEntry
        except ImportError:
            return FacultyResult(success=False, summary="LogEntry model not available", error="Model not found")

        query = params.get("query", "")
        logger_name = params.get("logger_name", "")
        level = params.get("level", "").upper()
        limit = params.get("limit", 50)
        hours = params.get("hours", 24)

        session = _session_factory()
        try:
            since = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=hours)

            q = session.query(LogEntry).filter(LogEntry.timestamp >= since)

            if query:
                q = q.filter(LogEntry.message.ilike(f"%{query}%"))

            if logger_name:
                q = q.filter(LogEntry.logger_name.ilike(f"%{logger_name}%"))

            if level:
                q = q.filter(LogEntry.level == level)

            logs = q.order_by(LogEntry.timestamp.desc()).limit(limit).all()

            if not logs:
                filters = []
                if query:
                    filters.append(f"query='{query}'")
                if logger_name:
                    filters.append(f"logger='{logger_name}'")
                if level:
                    filters.append(f"level={level}")
                filter_str = ", ".join(filters) if filters else "none"
                return FacultyResult(
                    success=True,
                    summary=f"No logs found in the last {hours}h with filters: {filter_str}",
                    data={"logs": []},
                )

            formatted = []
            for log in logs:
                ts = log.timestamp.strftime("%m-%d %H:%M:%S")
                msg = log.message[:200] + ("..." if len(log.message) > 200 else "")
                entry = f"[{ts}] **{log.level}** `{log.logger_name}`: {msg}"
                if log.exception:
                    exc_lines = log.exception.strip().split("\n")[-3:]
                    entry += f"\n```\n" + "\n".join(exc_lines) + "\n```"
                formatted.append(entry)

            return FacultyResult(
                success=True,
                summary=f"Found {len(logs)} log entries:\n\n" + "\n".join(formatted),
                data={"logs": [{"level": l.level, "message": l.message[:100]} for l in logs]},
            )

        finally:
            session.close()

    async def _get_recent(self, params: dict) -> FacultyResult:
        """Get the most recent log entries."""
        try:
            from db.models import LogEntry
        except ImportError:
            return FacultyResult(success=False, summary="LogEntry model not available", error="Model not found")

        limit = min(params.get("limit", 30), 100)
        logger_name = params.get("logger_name", "")

        session = _session_factory()
        try:
            q = session.query(LogEntry)

            if logger_name:
                q = q.filter(LogEntry.logger_name.ilike(f"%{logger_name}%"))

            logs = q.order_by(LogEntry.timestamp.desc()).limit(limit).all()

            if not logs:
                return FacultyResult(
                    success=True,
                    summary="No log entries found.",
                    data={"logs": []},
                )

            formatted = []
            for log in logs:
                ts = log.timestamp.strftime("%m-%d %H:%M:%S")
                msg = log.message[:150] + ("..." if len(log.message) > 150 else "")
                formatted.append(f"[{ts}] {log.level:8} `{log.logger_name}`: {msg}")

            return FacultyResult(
                success=True,
                summary=f"Last {len(logs)} log entries:\n\n" + "\n".join(formatted),
                data={"logs": [{"level": l.level, "message": l.message[:100]} for l in logs]},
            )

        finally:
            session.close()

    async def _get_errors(self, params: dict) -> FacultyResult:
        """Get recent error and exception logs."""
        try:
            from db.models import LogEntry
        except ImportError:
            return FacultyResult(success=False, summary="LogEntry model not available", error="Model not found")

        limit = min(params.get("limit", 20), 50)
        hours = params.get("hours", 24)
        include_warnings = params.get("include_warnings", False)

        session = _session_factory()
        try:
            since = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=hours)

            levels = ["ERROR", "CRITICAL"]
            if include_warnings:
                levels.append("WARNING")

            logs = (
                session.query(LogEntry)
                .filter(LogEntry.timestamp >= since)
                .filter(LogEntry.level.in_(levels))
                .order_by(LogEntry.timestamp.desc())
                .limit(limit)
                .all()
            )

            if not logs:
                return FacultyResult(
                    success=True,
                    summary=f"No errors found in the last {hours} hours.",
                    data={"logs": []},
                )

            formatted = []
            for log in logs:
                ts = log.timestamp.strftime("%m-%d %H:%M:%S")
                entry = f"### [{ts}] {log.level} - `{log.logger_name}`\n{log.message}"
                if log.exception:
                    entry += f"\n```\n{log.exception[:500]}\n```"
                formatted.append(entry)

            return FacultyResult(
                success=True,
                summary=f"Found {len(logs)} error(s) in the last {hours}h:\n\n" + "\n\n".join(formatted),
                data={"logs": [{"level": l.level, "message": l.message[:100]} for l in logs]},
            )

        finally:
            session.close()

    async def _get_by_logger(self, params: dict) -> FacultyResult:
        """Get logs from a specific logger/module."""
        logger_name = params.get("logger_name", "")
        if not logger_name:
            return FacultyResult(success=False, summary="No logger name specified", error="Missing logger_name")

        return await self._get_recent({"logger_name": logger_name, "limit": params.get("limit", 30)})
