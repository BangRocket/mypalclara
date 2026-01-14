"""Memory type classification and temporal weighting.

Provides:
- Memory type taxonomy with configurable decay rates
- Classification heuristics for new memories
- Recency weighting for temporal-aware retrieval
- Rich memory formatting for context injection
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


class MemoryType(str, Enum):
    """Memory type taxonomy with semantic meaning.

    Simplified to three buckets for Phase 1:
    - STABLE: Core identity, preferences - slow decay
    - ACTIVE: Current projects, ongoing work - medium decay
    - EPHEMERAL: Temporary states, events - fast decay
    """

    STABLE = "stable"  # Identity, preferences, relationships
    ACTIVE = "active"  # Projects, current work, ongoing efforts
    EPHEMERAL = "ephemeral"  # Status, events, temporary states

    @property
    def half_life_days(self) -> float:
        """Decay half-life in days for this memory type."""
        return DECAY_CONFIG[self]

    @property
    def display_label(self) -> str:
        """Human-readable label for context display."""
        return {
            MemoryType.STABLE: "stable",
            MemoryType.ACTIVE: "active",
            MemoryType.EPHEMERAL: "temp",
        }[self]


# Decay configuration: half-life in days per memory type
# After half_life_days, the recency weight drops to 0.5
DECAY_CONFIG: dict[MemoryType, float] = {
    MemoryType.STABLE: 60.0,  # Identity/preferences decay slowly
    MemoryType.ACTIVE: 14.0,  # Projects decay in ~2 weeks
    MemoryType.EPHEMERAL: 7.0,  # Events/status decay in ~1 week
}

# Minimum weight floor - prevents old important memories from disappearing
RECENCY_FLOOR = 0.1


@dataclass
class MemoryRecord:
    """Rich memory record with metadata for temporal-aware retrieval.

    Holds the full context needed for:
    - Recency-weighted scoring
    - Rich context formatting
    - Type-based filtering
    """

    id: str
    content: str
    memory_type: MemoryType
    created_at: datetime | None
    updated_at: datetime | None
    score: float  # Semantic similarity score from vector search
    metadata: dict[str, Any] | None = None

    @property
    def age_days(self) -> float:
        """Age in days since last update (or creation)."""
        timestamp = self.updated_at or self.created_at
        if not timestamp:
            return 0.0
        now = datetime.now(timezone.utc)
        # Handle naive datetimes by assuming UTC
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return (now - timestamp).total_seconds() / 86400

    @property
    def recency_weight(self) -> float:
        """Recency weight based on age and memory type decay rate."""
        return recency_weight(
            self.updated_at or self.created_at,
            half_life_days=self.memory_type.half_life_days,
        )

    @property
    def weighted_score(self) -> float:
        """Combined score: semantic similarity * recency weight."""
        return self.score * self.recency_weight

    def format_for_context(self) -> str:
        """Format memory for injection into LLM context.

        Returns format: [age | type] content
        Examples:
            [2 days ago | active] User is working on Clara's memory system
            [3 weeks ago | stable] User's wife is named Sarah
        """
        age_str = humanize_age(self.updated_at or self.created_at)
        type_label = self.memory_type.display_label
        return f"[{age_str} | {type_label}] {self.content}"


def recency_weight(
    timestamp: datetime | None,
    half_life_days: float = 14.0,
) -> float:
    """Calculate recency weight using exponential decay.

    Args:
        timestamp: When the memory was last updated (or created)
        half_life_days: Days until weight drops to 0.5

    Returns:
        Weight between RECENCY_FLOOR and 1.0
        - Today: ~1.0
        - half_life_days ago: ~0.5
        - 2x half_life_days ago: ~0.25
        - Very old: RECENCY_FLOOR (never fully zero)
    """
    if timestamp is None:
        return 1.0  # No timestamp = assume current

    now = datetime.now(timezone.utc)

    # Handle naive datetimes by assuming UTC
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    age_days = (now - timestamp).total_seconds() / 86400

    if age_days <= 0:
        return 1.0

    weight = math.pow(0.5, age_days / half_life_days)
    return max(weight, RECENCY_FLOOR)


def humanize_age(timestamp: datetime | None) -> str:
    """Convert timestamp to human-readable age string.

    Examples:
        - "just now" (< 1 hour)
        - "today" (< 24 hours)
        - "yesterday"
        - "3 days ago"
        - "2 weeks ago"
        - "1 month ago"
        - "6 months ago"
    """
    if timestamp is None:
        return "unknown"

    now = datetime.now(timezone.utc)

    # Handle naive datetimes
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    delta = now - timestamp
    days = delta.days
    hours = delta.seconds // 3600

    if days == 0:
        if hours < 1:
            return "just now"
        return "today"
    elif days == 1:
        return "yesterday"
    elif days < 7:
        return f"{days} days ago"
    elif days < 14:
        return "1 week ago"
    elif days < 30:
        weeks = days // 7
        return f"{weeks} weeks ago"
    elif days < 60:
        return "1 month ago"
    elif days < 365:
        months = days // 30
        return f"{months} months ago"
    else:
        years = days // 365
        return f"{years} year{'s' if years > 1 else ''} ago"


# Classification patterns - compiled for efficiency
_STABLE_PATTERNS = re.compile(
    r"\b(name is|wife|husband|daughter|son|partner|spouse|"
    r"married|family|parent|sibling|brother|sister|"
    r"prefers to be called|nickname|born|birthday|"
    r"lives in|home|address|always|never|"
    r"favorite|loves|hates|allergic|"
    r"profession|job title|works as|career)\b",
    re.IGNORECASE,
)

_ACTIVE_PATTERNS = re.compile(
    r"\b(working on|building|implementing|developing|"
    r"creating|writing|designing|planning|"
    r"project|task|sprint|milestone|"
    r"current|ongoing|active|in progress|"
    r"learning|studying|practicing|"
    r"goal|objective|target|deadline)\b",
    re.IGNORECASE,
)

_EPHEMERAL_PATTERNS = re.compile(
    r"\b(feeling|mood|stressed|overwhelmed|tired|exhausted|"
    r"excited|anxious|frustrated|happy|sad|angry|"
    r"today|tonight|this morning|this afternoon|"
    r"yesterday|last night|earlier|just|recently|"
    r"meeting|call|appointment|scheduled|"
    r"submitted|sent|received|completed|finished|"
    r"going to|about to|planning to|will be)\b",
    re.IGNORECASE,
)


def classify_memory(content: str) -> MemoryType:
    """Classify a memory into a type based on content patterns.

    Uses keyword heuristics as a starting point.
    Order matters: check ephemeral first (most specific),
    then active, then stable, with stable as default.

    Args:
        content: The memory text to classify

    Returns:
        MemoryType indicating the classification
    """
    # Count pattern matches for each type
    ephemeral_matches = len(_EPHEMERAL_PATTERNS.findall(content))
    active_matches = len(_ACTIVE_PATTERNS.findall(content))
    stable_matches = len(_STABLE_PATTERNS.findall(content))

    # Highest match count wins, with tie-breaking priority
    if ephemeral_matches > 0 and ephemeral_matches >= active_matches:
        # Ephemeral signals are strong - temporary states
        return MemoryType.EPHEMERAL

    if active_matches > stable_matches:
        return MemoryType.ACTIVE

    if stable_matches > 0:
        return MemoryType.STABLE

    # Default: treat unknown as active (medium decay)
    # Better to decay than to persist stale info
    return MemoryType.ACTIVE


def classify_memory_batch(memories: list[str]) -> list[MemoryType]:
    """Classify multiple memories efficiently.

    Args:
        memories: List of memory content strings

    Returns:
        List of MemoryType classifications in same order
    """
    return [classify_memory(m) for m in memories]
