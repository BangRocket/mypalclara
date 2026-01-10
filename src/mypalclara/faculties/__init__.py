"""
Clara's faculties - skilled capabilities for action.

Faculties are not autonomous agents. They know HOW to do things,
not WHETHER to. The decision to act lives in Ruminate.
"""

from mypalclara.faculties.base import Faculty, FacultyResult
from mypalclara.faculties.github import GitHubFaculty

# Registry of available faculties
FACULTIES: dict[str, "Faculty"] = {
    "github": GitHubFaculty(),
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
]
