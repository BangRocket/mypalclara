"""
Clara's faculties - skilled capabilities for action.

Faculties are not autonomous agents. They know HOW to do things,
not WHETHER to. The decision to act lives in Ruminate.
"""

from mypalclara.faculties.base import Faculty
from mypalclara.models.state import FacultyResult

# Import all faculties
from mypalclara.faculties.github_faculty import GitHubFaculty
from mypalclara.faculties.browser import BrowserFaculty
from mypalclara.faculties.code import CodeFaculty
from mypalclara.faculties.files import FilesFaculty
from mypalclara.faculties.google import GoogleFaculty
from mypalclara.faculties.mail import EmailFaculty
from mypalclara.faculties.ado import AdoFaculty
from mypalclara.faculties.history import HistoryFaculty
from mypalclara.faculties.logs import LogsFaculty
from mypalclara.faculties.discord import DiscordFaculty

# Registry of available faculties
FACULTIES: dict[str, "Faculty"] = {
    "github": GitHubFaculty(),
    "browser": BrowserFaculty(),
    "code": CodeFaculty(),
    "files": FilesFaculty(),
    "google": GoogleFaculty(),
    "email": EmailFaculty(),
    "ado": AdoFaculty(),
    "history": HistoryFaculty(),
    "logs": LogsFaculty(),
    "discord": DiscordFaculty(),
}


def register_faculty(faculty: "Faculty") -> None:
    """Register a faculty for use by Clara."""
    FACULTIES[faculty.name] = faculty


def get_faculty(name: str) -> "Faculty | None":
    """Get a faculty by name."""
    return FACULTIES.get(name)


def list_faculties() -> list[str]:
    """List available faculty names."""
    return list(FACULTIES.keys())


__all__ = [
    "Faculty",
    "FacultyResult",
    "register_faculty",
    "get_faculty",
    "list_faculties",
    # Individual faculties
    "GitHubFaculty",
    "BrowserFaculty",
    "CodeFaculty",
    "FilesFaculty",
    "GoogleFaculty",
    "EmailFaculty",
    "AdoFaculty",
    "HistoryFaculty",
    "LogsFaculty",
    "DiscordFaculty",
]
