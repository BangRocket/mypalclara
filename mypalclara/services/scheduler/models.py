"""Data models for the task scheduler."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class TaskType(str, Enum):
    CRON = "cron"
    ONE_SHOT = "one_shot"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ScheduledTask:
    """A task scheduled for future or recurring execution."""

    id: str
    type: TaskType
    prompt: str
    user_id: str
    channel_id: str
    run_at: datetime | None = None
    cron_expr: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_run_at: datetime | None = None
    description: str = ""
