"""Tests for the task scheduler service."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from mypalclara.services.scheduler import ScheduledTask, Scheduler, TaskStatus, TaskType


def _make_task(
    *,
    task_type: TaskType = TaskType.ONE_SHOT,
    prompt: str = "test prompt",
    run_at: datetime | None = None,
    cron_expr: str | None = None,
    status: TaskStatus = TaskStatus.PENDING,
    user_id: str = "user-1",
    channel_id: str = "ch-1",
) -> ScheduledTask:
    return ScheduledTask(
        id="task-1",
        type=task_type,
        prompt=prompt,
        user_id=user_id,
        channel_id=channel_id,
        run_at=run_at,
        cron_expr=cron_expr,
        status=status,
    )


class TestOneShot:
    """One-shot task fires at the right time."""

    @pytest.mark.asyncio
    async def test_fires_when_due(self) -> None:
        dispatched: list[ScheduledTask] = []

        async def capture(task: ScheduledTask) -> None:
            dispatched.append(task)

        scheduler = Scheduler(dispatch_fn=capture, tick_interval=0.05)
        past = datetime.now(UTC) - timedelta(seconds=1)
        task = _make_task(run_at=past)
        scheduler.add_task(task)

        # Run for a short time, then stop
        run_task = asyncio.create_task(scheduler.run())
        await asyncio.sleep(0.15)
        scheduler.stop()
        await run_task

        assert len(dispatched) == 1
        assert dispatched[0].id == "task-1"
        # One-shot should be marked completed
        stored = scheduler.get_task("task-1")
        assert stored is not None
        assert stored.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_does_not_fire_before_due(self) -> None:
        dispatched: list[ScheduledTask] = []

        async def capture(task: ScheduledTask) -> None:
            dispatched.append(task)

        scheduler = Scheduler(dispatch_fn=capture, tick_interval=0.05)
        future = datetime.now(UTC) + timedelta(hours=1)
        task = _make_task(run_at=future)
        scheduler.add_task(task)

        run_task = asyncio.create_task(scheduler.run())
        await asyncio.sleep(0.15)
        scheduler.stop()
        await run_task

        assert len(dispatched) == 0
        stored = scheduler.get_task("task-1")
        assert stored is not None
        assert stored.status == TaskStatus.PENDING


class TestListAndRemoval:
    """Task list and removal."""

    def test_add_list_remove(self) -> None:
        async def noop(task: ScheduledTask) -> None:
            pass

        scheduler = Scheduler(dispatch_fn=noop)

        t1 = _make_task(user_id="alice")
        t1.id = "t1"
        t2 = _make_task(user_id="bob")
        t2.id = "t2"
        t3 = _make_task(user_id="alice")
        t3.id = "t3"

        scheduler.add_task(t1)
        scheduler.add_task(t2)
        scheduler.add_task(t3)

        # List all
        assert len(scheduler.list_tasks()) == 3

        # List by user
        assert len(scheduler.list_tasks(user_id="alice")) == 2
        assert len(scheduler.list_tasks(user_id="bob")) == 1

        # Remove
        assert scheduler.remove_task("t2") is True
        assert len(scheduler.list_tasks()) == 2
        assert scheduler.get_task("t2") is None

        # Remove nonexistent
        assert scheduler.remove_task("nonexistent") is False


class TestCronNextRun:
    """Cron task calculates next run."""

    def test_next_cron_run_every_5_minutes(self) -> None:
        async def noop(task: ScheduledTask) -> None:
            pass

        scheduler = Scheduler(dispatch_fn=noop)
        base = datetime(2026, 3, 20, 12, 0, 0, tzinfo=UTC)
        next_run = scheduler._next_cron_run("*/5 * * * *", after=base)
        assert next_run == datetime(2026, 3, 20, 12, 5, 0, tzinfo=UTC)

    def test_next_cron_run_hourly(self) -> None:
        async def noop(task: ScheduledTask) -> None:
            pass

        scheduler = Scheduler(dispatch_fn=noop)
        base = datetime(2026, 3, 20, 12, 30, 0, tzinfo=UTC)
        next_run = scheduler._next_cron_run("0 * * * *", after=base)
        assert next_run == datetime(2026, 3, 20, 13, 0, 0, tzinfo=UTC)

    def test_next_cron_run_daily(self) -> None:
        async def noop(task: ScheduledTask) -> None:
            pass

        scheduler = Scheduler(dispatch_fn=noop)
        base = datetime(2026, 3, 20, 15, 0, 0, tzinfo=UTC)
        next_run = scheduler._next_cron_run("0 9 * * *", after=base)
        # Next 9:00 is the next day
        assert next_run == datetime(2026, 3, 21, 9, 0, 0, tzinfo=UTC)


class TestDueCheck:
    """Due-check logic."""

    def test_one_shot_due(self) -> None:
        async def noop(task: ScheduledTask) -> None:
            pass

        scheduler = Scheduler(dispatch_fn=noop)
        past = datetime.now(UTC) - timedelta(seconds=10)
        task = _make_task(run_at=past)
        assert scheduler._is_due(task) is True

    def test_one_shot_not_due(self) -> None:
        async def noop(task: ScheduledTask) -> None:
            pass

        scheduler = Scheduler(dispatch_fn=noop)
        future = datetime.now(UTC) + timedelta(hours=1)
        task = _make_task(run_at=future)
        assert scheduler._is_due(task) is False

    def test_completed_not_due(self) -> None:
        async def noop(task: ScheduledTask) -> None:
            pass

        scheduler = Scheduler(dispatch_fn=noop)
        past = datetime.now(UTC) - timedelta(seconds=10)
        task = _make_task(run_at=past, status=TaskStatus.COMPLETED)
        assert scheduler._is_due(task) is False

    def test_cron_due(self) -> None:
        async def noop(task: ScheduledTask) -> None:
            pass

        scheduler = Scheduler(dispatch_fn=noop)
        past = datetime.now(UTC) - timedelta(seconds=10)
        task = _make_task(
            task_type=TaskType.CRON,
            cron_expr="*/5 * * * *",
            run_at=past,
        )
        assert scheduler._is_due(task) is True

    def test_cron_no_run_at_is_due(self) -> None:
        """A cron task with no run_at should be considered due (needs initial scheduling)."""

        async def noop(task: ScheduledTask) -> None:
            pass

        scheduler = Scheduler(dispatch_fn=noop)
        task = _make_task(
            task_type=TaskType.CRON,
            cron_expr="*/5 * * * *",
            run_at=None,
        )
        assert scheduler._is_due(task) is True
