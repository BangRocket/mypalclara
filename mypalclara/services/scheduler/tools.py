"""Tool definitions for scheduler management."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from .models import ScheduledTask, TaskStatus, TaskType
from .scheduler import Scheduler

SCHEDULER_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "schedule_task",
            "description": (
                "Schedule a one-shot task to run at a specific time. "
                "The task dispatches a prompt through the gateway pipeline."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The prompt to dispatch when the task fires.",
                    },
                    "run_at": {
                        "type": "string",
                        "description": "ISO 8601 datetime for when to run (e.g. '2026-03-20T15:00:00Z').",
                    },
                    "description": {
                        "type": "string",
                        "description": "Human-readable description of the task.",
                    },
                },
                "required": ["prompt", "run_at"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_cron",
            "description": (
                "Schedule a recurring task using a cron expression. "
                "The task dispatches a prompt through the gateway pipeline on each fire."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "The prompt to dispatch on each fire.",
                    },
                    "cron_expr": {
                        "type": "string",
                        "description": "Standard 5-field cron expression (e.g. '*/30 * * * *' for every 30 min).",
                    },
                    "description": {
                        "type": "string",
                        "description": "Human-readable description of the recurring task.",
                    },
                },
                "required": ["prompt", "cron_expr"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_scheduled_tasks",
            "description": "List all scheduled tasks (both one-shot and recurring).",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_scheduled_task",
            "description": "Cancel and remove a scheduled task by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The ID of the task to cancel.",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
]


def handle_scheduler_tool(
    tool_name: str,
    args: dict[str, Any],
    scheduler: Scheduler,
    user_id: str,
    channel_id: str,
) -> str:
    """Dispatch a scheduler tool call and return a human-readable result.

    Args:
        tool_name: One of the scheduler tool names.
        args: Tool arguments.
        scheduler: The active Scheduler instance.
        user_id: The calling user's ID.
        channel_id: The channel where the tool was invoked.

    Returns:
        A string result message.
    """
    if tool_name == "schedule_task":
        return _handle_schedule_task(args, scheduler, user_id, channel_id)
    if tool_name == "schedule_cron":
        return _handle_schedule_cron(args, scheduler, user_id, channel_id)
    if tool_name == "list_scheduled_tasks":
        return _handle_list(scheduler, user_id)
    if tool_name == "cancel_scheduled_task":
        return _handle_cancel(args, scheduler)
    return f"Unknown scheduler tool: {tool_name}"


def _handle_schedule_task(
    args: dict[str, Any],
    scheduler: Scheduler,
    user_id: str,
    channel_id: str,
) -> str:
    prompt = args["prompt"]
    run_at_str = args["run_at"]
    description = args.get("description", "")

    try:
        run_at = datetime.fromisoformat(run_at_str)
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=UTC)
    except ValueError:
        return f"Invalid datetime format: {run_at_str!r}. Use ISO 8601 (e.g. '2026-03-20T15:00:00Z')."

    task_id = f"task-{uuid.uuid4().hex[:8]}"
    task = ScheduledTask(
        id=task_id,
        type=TaskType.ONE_SHOT,
        prompt=prompt,
        user_id=user_id,
        channel_id=channel_id,
        run_at=run_at,
        description=description,
    )
    scheduler.add_task(task)
    return f"Scheduled one-shot task {task_id} for {run_at.isoformat()}: {description or prompt[:60]}"


def _handle_schedule_cron(
    args: dict[str, Any],
    scheduler: Scheduler,
    user_id: str,
    channel_id: str,
) -> str:
    prompt = args["prompt"]
    cron_expr = args["cron_expr"]
    description = args.get("description", "")

    task_id = f"cron-{uuid.uuid4().hex[:8]}"
    task = ScheduledTask(
        id=task_id,
        type=TaskType.CRON,
        prompt=prompt,
        user_id=user_id,
        channel_id=channel_id,
        cron_expr=cron_expr,
        description=description,
    )
    scheduler.add_task(task)
    return f"Scheduled recurring task {task_id} ({cron_expr}): {description or prompt[:60]}"


def _handle_list(scheduler: Scheduler, user_id: str) -> str:
    tasks = scheduler.list_tasks(user_id=user_id)
    if not tasks:
        return "No scheduled tasks."
    lines = []
    for t in tasks:
        kind = "cron" if t.type == TaskType.CRON else "one-shot"
        schedule = t.cron_expr if t.type == TaskType.CRON else (t.run_at.isoformat() if t.run_at else "unset")
        desc = t.description or t.prompt[:40]
        lines.append(f"- {t.id} [{kind}, {t.status.value}] {schedule} — {desc}")
    return "\n".join(lines)


def _handle_cancel(args: dict[str, Any], scheduler: Scheduler) -> str:
    task_id = args["task_id"]
    if scheduler.remove_task(task_id):
        return f"Cancelled task {task_id}."
    return f"No task found with ID {task_id}."
