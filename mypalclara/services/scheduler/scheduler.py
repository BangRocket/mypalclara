"""Scheduler service for cron and one-shot tasks."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, Callable

from .models import ScheduledTask, TaskStatus, TaskType

try:
    from croniter import croniter as _croniter  # type: ignore[import-untyped]

    _HAS_CRONITER = True
except ImportError:
    _HAS_CRONITER = False

logger = logging.getLogger(__name__)


class Scheduler:
    """In-memory task scheduler supporting cron and one-shot tasks.

    Args:
        dispatch_fn: Async callable invoked with a ScheduledTask when it fires.
        tick_interval: Seconds between checks for due tasks.
    """

    def __init__(
        self,
        dispatch_fn: Callable[[ScheduledTask], Any],
        tick_interval: float = 1.0,
    ) -> None:
        self._dispatch_fn = dispatch_fn
        self._tick_interval = tick_interval
        self._tasks: dict[str, ScheduledTask] = {}
        self._running = False

    # -- public API ----------------------------------------------------------

    def add_task(self, task: ScheduledTask) -> None:
        """Register a task with the scheduler."""
        if task.type == TaskType.CRON and task.run_at is None:
            # Calculate initial run_at from cron expression
            if task.cron_expr:
                task.run_at = self._next_cron_run(task.cron_expr, after=datetime.now(UTC))
        self._tasks[task.id] = task

    def remove_task(self, task_id: str) -> bool:
        """Remove a task. Returns True if it existed."""
        return self._tasks.pop(task_id, None) is not None

    def list_tasks(self, user_id: str | None = None) -> list[ScheduledTask]:
        """List tasks, optionally filtered by user_id."""
        tasks = list(self._tasks.values())
        if user_id is not None:
            tasks = [t for t in tasks if t.user_id == user_id]
        return tasks

    def get_task(self, task_id: str) -> ScheduledTask | None:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    async def run(self) -> None:
        """Main event loop. Checks for due tasks each tick."""
        self._running = True
        logger.info("Scheduler started (tick=%.2fs)", self._tick_interval)
        while self._running:
            await self._tick()
            await asyncio.sleep(self._tick_interval)
        logger.info("Scheduler stopped")

    def stop(self) -> None:
        """Signal the run loop to stop."""
        self._running = False

    # -- internals -----------------------------------------------------------

    async def _tick(self) -> None:
        """Check all tasks and dispatch those that are due."""
        for task in list(self._tasks.values()):
            if not self._is_due(task):
                continue
            task.status = TaskStatus.RUNNING
            try:
                await self._dispatch_fn(task)
                task.last_run_at = datetime.now(UTC)
                if task.type == TaskType.ONE_SHOT:
                    task.status = TaskStatus.COMPLETED
                elif task.type == TaskType.CRON and task.cron_expr:
                    task.status = TaskStatus.PENDING
                    task.run_at = self._next_cron_run(task.cron_expr, after=datetime.now(UTC))
            except Exception:
                logger.exception("Task %s dispatch failed", task.id)
                task.status = TaskStatus.FAILED

    def _is_due(self, task: ScheduledTask) -> bool:
        """Check if a task should fire now."""
        if task.status in (TaskStatus.COMPLETED, TaskStatus.RUNNING):
            return False
        if task.run_at is None:
            # Cron task without computed run_at — treat as immediately due
            return task.type == TaskType.CRON
        return datetime.now(UTC) >= task.run_at

    def _next_cron_run(self, cron_expr: str, after: datetime) -> datetime:
        """Calculate next run time from a cron expression.

        Uses croniter if available, otherwise falls back to a simple parser
        supporting standard 5-field cron expressions.
        """
        if _HAS_CRONITER:
            cron = _croniter(cron_expr, after)
            return cron.get_next(datetime).replace(tzinfo=UTC)
        return _simple_cron_next(cron_expr, after)


# ---------------------------------------------------------------------------
# Simple cron fallback (no croniter dependency)
# ---------------------------------------------------------------------------


def _parse_cron_field(field: str, min_val: int, max_val: int) -> list[int]:
    """Parse a single cron field into a sorted list of matching values.

    Supports: *, */N, N, N-M, N-M/S, and comma-separated combinations.
    """
    values: set[int] = set()
    for part in field.split(","):
        if "/" in part:
            base, step_str = part.split("/", 1)
            step = int(step_str)
            if base == "*":
                start, end = min_val, max_val
            elif "-" in base:
                start, end = (int(x) for x in base.split("-", 1))
            else:
                start, end = int(base), max_val
            values.update(range(start, end + 1, step))
        elif part == "*":
            values.update(range(min_val, max_val + 1))
        elif "-" in part:
            start, end = (int(x) for x in part.split("-", 1))
            values.update(range(start, end + 1))
        else:
            values.add(int(part))
    return sorted(values)


def _simple_cron_next(cron_expr: str, after: datetime) -> datetime:
    """Compute next cron fire time using a simple field matcher.

    Supports standard 5-field cron: minute hour day-of-month month day-of-week.
    """
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Expected 5-field cron expression, got {len(parts)}: {cron_expr!r}")

    minutes = _parse_cron_field(parts[0], 0, 59)
    hours = _parse_cron_field(parts[1], 0, 23)
    # We only need minute and hour for the common cases; day/month/dow
    # are checked but we iterate forward minute-by-minute for correctness.
    days = _parse_cron_field(parts[2], 1, 31)
    months = _parse_cron_field(parts[3], 1, 12)
    # day-of-week: 0=Sunday in cron, but isoweekday is 1=Mon..7=Sun
    dow_raw = _parse_cron_field(parts[4], 0, 6)
    # Convert cron dow (0=Sun,1=Mon..6=Sat) to isoweekday (1=Mon..7=Sun)
    dow = {(d % 7) or 7 for d in dow_raw}  # 0->7 (Sun), 1->1, etc.
    dow_is_star = parts[4] == "*"

    # Start from one minute after `after`, scan forward up to 1 year
    candidate = after.replace(second=0, microsecond=0)
    from datetime import timedelta

    candidate += timedelta(minutes=1)
    limit = after + timedelta(days=366)

    while candidate < limit:
        if (
            candidate.minute in minutes
            and candidate.hour in hours
            and candidate.month in months
            and candidate.day in days
            and (dow_is_star or candidate.isoweekday() in dow)
        ):
            return candidate.replace(tzinfo=UTC)
        candidate += timedelta(minutes=1)

    raise ValueError(f"Could not find next run for cron expression {cron_expr!r} within 1 year")
