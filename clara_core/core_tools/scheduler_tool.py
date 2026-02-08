"""Schedule management tool - Clara core tool.

Exposes the gateway scheduler to the LLM so it can create, list, and cancel
scheduled tasks — reminders, recurring follow-ups, and one-shot future messages.

When a scheduled task fires, the handler sends a ProactiveMessage through the
gateway bridge to the user's channel.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from config.logging import get_logger
from tools._base import ToolContext, ToolDef

MODULE_NAME = "scheduler"
MODULE_VERSION = "1.0.0"

logger = get_logger("core_tools.scheduler")

SYSTEM_PROMPT = """## Schedule Management
You can create reminders, scheduled follow-ups, and recurring tasks using the `manage_schedule` tool.
- Use delay_minutes for one-time future messages (e.g., reminders in 2 hours)
- Use cron for recurring schedules (e.g., "0 9 * * 1-5" for weekday 9 AM)
- Task names are auto-generated as "user-{slug}" to avoid collisions
- You can only list/cancel tasks that were created through this tool (user-scoped)
""".strip()

# Prefix for user-created tasks so we can scope list/cancel
_USER_TASK_PREFIX = "user-"


def _slugify(text: str) -> str:
    """Convert text to a short slug for task names."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower().strip())
    return slug[:40].strip("-")


async def _send_scheduled_message(
    user_id: str,
    channel_id: str,
    message: str,
    description: str,
) -> None:
    """Handler called when a scheduled task fires.

    Sends a message via the scheduler's gateway server connection.
    """
    from mypalclara.gateway.scheduler import get_scheduler

    scheduler = get_scheduler()
    success = await scheduler.send_message(
        user_id=user_id,
        channel_id=channel_id,
        message=message,
        purpose=f"Scheduled: {description}",
    )
    if success:
        logger.info(f"Scheduled message delivered for {user_id}: {description[:50]}")
    else:
        logger.warning(
            f"Scheduler: failed to deliver message for " f"user={user_id} channel={channel_id}: {message[:60]}"
        )


async def _handle_manage_schedule(args: dict[str, Any], ctx: ToolContext) -> str:
    """Handle all schedule management actions."""
    from mypalclara.gateway.scheduler import (
        ScheduledTask,
        TaskType,
        get_scheduler,
    )

    action = args.get("action", "list")
    scheduler = get_scheduler()

    if action == "list":
        tasks = scheduler.get_tasks()
        user_tasks = [t for t in tasks if t.name.startswith(_USER_TASK_PREFIX)]

        if not user_tasks:
            return "No scheduled tasks. Use action 'create' to set one up."

        lines = []
        for t in user_tasks:
            status = "enabled" if t.enabled else "disabled"
            next_run = t.next_run.strftime("%Y-%m-%d %H:%M") if t.next_run else "none"
            type_label = t.type.value
            lines.append(f"- **{t.name}** [{type_label}, {status}] next: {next_run} — {t.description}")

        return f"**Scheduled tasks ({len(user_tasks)}):**\n" + "\n".join(lines)

    elif action == "create":
        description = args.get("description")
        delay_minutes = args.get("delay_minutes")
        cron = args.get("cron")
        message = args.get("message")
        channel_id = args.get("channel_id") or ctx.channel_id

        if not description:
            return "Error: 'create' requires a description of what this schedule does."
        if not message:
            return "Error: 'create' requires a message to send when the task fires."
        if not channel_id:
            return "Error: No channel_id available. Specify channel_id explicitly."
        if delay_minutes is None and cron is None:
            return "Error: Provide either delay_minutes (one-shot) or cron (recurring)."
        if delay_minutes is not None and cron is not None:
            return "Error: Provide delay_minutes OR cron, not both."

        slug = _slugify(description)
        task_name = f"{_USER_TASK_PREFIX}{slug}"

        # Check for name collision
        existing = scheduler.get_task(task_name)
        if existing:
            return (
                f"Error: A task named '{task_name}' already exists. " f"Cancel it first or use a different description."
            )

        user_id = ctx.user_id

        # Build the async handler closure
        async def handler(
            _uid: str = user_id,
            _cid: str = channel_id,
            _msg: str = message,
            _desc: str = description,
        ) -> None:
            await _send_scheduled_message(_uid, _cid, _msg, _desc)

        if delay_minutes is not None:
            # One-shot task
            try:
                delay_minutes = int(delay_minutes)
            except (ValueError, TypeError):
                return "Error: delay_minutes must be an integer."
            if delay_minutes < 1:
                return "Error: delay_minutes must be at least 1."

            task = ScheduledTask(
                name=task_name,
                type=TaskType.ONE_SHOT,
                handler=handler,
                delay=delay_minutes * 60,
                description=description,
            )
            scheduler.add_task(task)

            fire_time = datetime.now() + timedelta(minutes=delay_minutes)
            return (
                f"Scheduled one-shot task **{task_name}**.\n"
                f"- Fires at: {fire_time.strftime('%Y-%m-%d %H:%M')}\n"
                f"- Message: {message}\n"
                f"- Channel: {channel_id}"
            )

        else:
            # Recurring cron task
            task = ScheduledTask(
                name=task_name,
                type=TaskType.CRON,
                handler=handler,
                cron=cron,
                description=description,
            )
            try:
                scheduler.add_task(task)
            except Exception as e:
                return f"Error: Invalid cron expression '{cron}': {e}"

            next_run = task.next_run.strftime("%Y-%m-%d %H:%M") if task.next_run else "unknown"
            return (
                f"Scheduled recurring task **{task_name}**.\n"
                f"- Cron: `{cron}`\n"
                f"- Next run: {next_run}\n"
                f"- Message: {message}\n"
                f"- Channel: {channel_id}"
            )

    elif action == "cancel":
        task_name = args.get("task_name")
        if not task_name:
            return "Error: 'cancel' requires task_name. Use action 'list' to see names."

        # Ensure it's a user-created task
        if not task_name.startswith(_USER_TASK_PREFIX):
            return f"Error: Can only cancel user-created tasks (prefix '{_USER_TASK_PREFIX}')."

        removed = scheduler.remove_task(task_name)
        if removed:
            return f"Cancelled task **{task_name}**."
        return f"Error: Task '{task_name}' not found."

    else:
        return f"Unknown action '{action}'. Valid: create, list, cancel"


TOOLS = [
    ToolDef(
        name="manage_schedule",
        description=(
            "Create, list, or cancel scheduled tasks — reminders, recurring follow-ups, "
            "and timed messages. Use delay_minutes for one-shot reminders or cron for "
            "recurring schedules."
        ),
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "list", "cancel"],
                    "description": "What to do: create a schedule, list active schedules, or cancel one",
                },
                "description": {
                    "type": "string",
                    "description": "Human-readable description of what this schedule does (required for create)",
                },
                "delay_minutes": {
                    "type": "integer",
                    "description": "Minutes from now for a one-shot task (e.g., 120 = remind in 2 hours)",
                },
                "cron": {
                    "type": "string",
                    "description": "Cron expression for recurring tasks (e.g., '0 9 * * 1-5' for weekday 9 AM)",
                },
                "message": {
                    "type": "string",
                    "description": "The message to send when the task fires (required for create)",
                },
                "channel_id": {
                    "type": "string",
                    "description": "Target channel ID (defaults to current channel)",
                },
                "task_name": {
                    "type": "string",
                    "description": "Name of the task to cancel (use 'list' to find names)",
                },
            },
            "required": ["action"],
        },
        handler=_handle_manage_schedule,
        emoji="\u23f0",
        label="Schedule",
        detail_keys=["action", "description"],
        risk_level="moderate",
        intent="write",
    ),
]


async def initialize() -> None:
    """Initialize scheduler tool module."""
    pass


async def cleanup() -> None:
    """Cleanup on module unload."""
    pass
