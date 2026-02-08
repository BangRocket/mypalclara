"""Schedule management tool - Clara core tool.

Exposes the gateway scheduler to the LLM so it can create, list, and cancel
scheduled tasks — reminders, recurring follow-ups, one-shot future messages,
and shell commands.

When a scheduled message task fires, the handler sends a ProactiveMessage
through the gateway bridge to the user's channel.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from config.logging import get_logger
from tools._base import ToolContext, ToolDef

MODULE_NAME = "scheduler"
MODULE_VERSION = "2.0.0"

logger = get_logger("core_tools.scheduler")

SYSTEM_PROMPT = """## Schedule Management
You can manage scheduled tasks using the `manage_schedule` tool.

**Creating tasks:**
- `delay_minutes` — one-shot task that fires once after N minutes
- `cron` — recurring task on a cron schedule (e.g., "0 9 * * 1-5" for weekday 9 AM)
- `interval_minutes` — recurring task every N minutes
- Exactly one timing option per task. They are mutually exclusive.

**Payload (choose one):**
- `message` + `channel_id` — send a message to a channel when the task fires
- `command` — run a shell command (optionally with `working_dir` and `timeout`)

**Other actions:**
- `list` — view all your scheduled tasks with status, next/last run, and run count
- `cancel` — remove a task permanently
- `enable` / `disable` — pause or resume a task without deleting it
- `run_now` — trigger a task immediately and see the result
- `results` — view recent execution history (success/fail, duration, output)
- `stats` — scheduler overview (total tasks, success rate, etc.)

Task names are auto-generated as "user-{slug}" to avoid collisions.
You can only manage tasks created through this tool (user-scoped).
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


def _enforce_user_scope(task_name: str) -> str | None:
    """Return an error string if task_name is not user-scoped, else None."""
    if not task_name:
        return "Error: task_name is required. Use action 'list' to see names."
    if not task_name.startswith(_USER_TASK_PREFIX):
        return f"Error: Can only manage user-created tasks (prefix '{_USER_TASK_PREFIX}')."
    return None


async def _handle_manage_schedule(args: dict[str, Any], ctx: ToolContext) -> str:
    """Handle all schedule management actions."""
    from mypalclara.gateway.scheduler import (
        ScheduledTask,
        TaskType,
        get_scheduler,
    )

    action = args.get("action", "list")
    scheduler = get_scheduler()

    # ------------------------------------------------------------------
    # LIST
    # ------------------------------------------------------------------
    if action == "list":
        tasks = scheduler.get_tasks()
        user_tasks = [t for t in tasks if t.name.startswith(_USER_TASK_PREFIX)]

        if not user_tasks:
            return "No scheduled tasks. Use action 'create' to set one up."

        lines = []
        for t in user_tasks:
            status = "enabled" if t.enabled else "disabled"
            next_run = t.next_run.strftime("%Y-%m-%d %H:%M") if t.next_run else "none"
            last_run = t.last_run.strftime("%Y-%m-%d %H:%M") if t.last_run else "never"
            running = t.name in scheduler._running_tasks
            type_label = t.type.value
            parts = [
                f"- **{t.name}** [{type_label}, {status}]",
                f"next: {next_run}",
                f"last: {last_run}",
                f"runs: {t.run_count}",
            ]
            if running:
                parts.append("(running now)")
            parts.append(f"— {t.description}")
            lines.append(" | ".join(parts))

        return f"**Scheduled tasks ({len(user_tasks)}):**\n" + "\n".join(lines)

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------
    elif action == "create":
        description = args.get("description")
        delay_minutes = args.get("delay_minutes")
        cron = args.get("cron")
        interval_minutes = args.get("interval_minutes")
        message = args.get("message")
        command = args.get("command")
        channel_id = args.get("channel_id") or ctx.channel_id
        working_dir = args.get("working_dir")
        timeout = args.get("timeout")

        if not description:
            return "Error: 'create' requires a description of what this schedule does."

        # --- Payload validation ---
        has_message = bool(message)
        has_command = bool(command)
        if not has_message and not has_command:
            return "Error: Provide either 'message' (to send) or 'command' (shell command to run)."
        if has_message and has_command:
            return "Error: Provide 'message' OR 'command', not both."
        if has_message and not channel_id:
            return "Error: No channel_id available for message delivery. Specify channel_id explicitly."
        if not has_command and (working_dir is not None or timeout is not None):
            return "Error: 'working_dir' and 'timeout' are only valid with 'command'."

        # --- Timing validation ---
        timing_count = sum(x is not None for x in [delay_minutes, cron, interval_minutes])
        if timing_count == 0:
            return "Error: Provide one timing option: delay_minutes, cron, or interval_minutes."
        if timing_count > 1:
            return "Error: Provide exactly one timing option (delay_minutes, cron, or interval_minutes)."

        slug = _slugify(description)
        task_name = f"{_USER_TASK_PREFIX}{slug}"

        # Check for name collision
        existing = scheduler.get_task(task_name)
        if existing:
            return (
                f"Error: A task named '{task_name}' already exists. " f"Cancel it first or use a different description."
            )

        user_id = ctx.user_id

        # --- Build task based on payload type ---
        if has_message:
            # Message-sending handler closure
            async def handler(
                _uid: str = user_id,
                _cid: str = channel_id,
                _msg: str = message,
                _desc: str = description,
            ) -> None:
                await _send_scheduled_message(_uid, _cid, _msg, _desc)

            task_kwargs: dict[str, Any] = {"handler": handler}
            payload_desc = f"Message: {message}\n- Channel: {channel_id}"
        else:
            # Shell command — use ScheduledTask.command field directly
            task_kwargs = {"command": command}
            if working_dir:
                task_kwargs["working_dir"] = working_dir
            if timeout is not None:
                try:
                    task_kwargs["timeout"] = float(timeout)
                except (ValueError, TypeError):
                    return "Error: timeout must be a number (seconds)."
            payload_desc = f"Command: `{command}`"
            if working_dir:
                payload_desc += f"\n- Working dir: {working_dir}"

        # --- Build task based on timing type ---
        if delay_minutes is not None:
            try:
                delay_minutes = int(delay_minutes)
            except (ValueError, TypeError):
                return "Error: delay_minutes must be an integer."
            if delay_minutes < 1:
                return "Error: delay_minutes must be at least 1."

            task = ScheduledTask(
                name=task_name,
                type=TaskType.ONE_SHOT,
                delay=delay_minutes * 60,
                description=description,
                **task_kwargs,
            )
            scheduler.add_task(task)

            fire_time = datetime.now() + timedelta(minutes=delay_minutes)
            return (
                f"Scheduled one-shot task **{task_name}**.\n"
                f"- Fires at: {fire_time.strftime('%Y-%m-%d %H:%M')}\n"
                f"- {payload_desc}"
            )

        elif interval_minutes is not None:
            try:
                interval_minutes = int(interval_minutes)
            except (ValueError, TypeError):
                return "Error: interval_minutes must be an integer."
            if interval_minutes < 1:
                return "Error: interval_minutes must be at least 1."

            task = ScheduledTask(
                name=task_name,
                type=TaskType.INTERVAL,
                interval=interval_minutes * 60,
                description=description,
                **task_kwargs,
            )
            scheduler.add_task(task)

            next_run = task.next_run.strftime("%Y-%m-%d %H:%M") if task.next_run else "unknown"
            return (
                f"Scheduled interval task **{task_name}** (every {interval_minutes} min).\n"
                f"- Next run: {next_run}\n"
                f"- {payload_desc}"
            )

        else:
            # Cron
            task = ScheduledTask(
                name=task_name,
                type=TaskType.CRON,
                cron=cron,
                description=description,
                **task_kwargs,
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
                f"- {payload_desc}"
            )

    # ------------------------------------------------------------------
    # CANCEL
    # ------------------------------------------------------------------
    elif action == "cancel":
        task_name = args.get("task_name")
        if err := _enforce_user_scope(task_name):
            return err

        removed = scheduler.remove_task(task_name)
        if removed:
            return f"Cancelled task **{task_name}**."
        return f"Error: Task '{task_name}' not found."

    # ------------------------------------------------------------------
    # ENABLE
    # ------------------------------------------------------------------
    elif action == "enable":
        task_name = args.get("task_name")
        if err := _enforce_user_scope(task_name):
            return err

        if scheduler.enable_task(task_name):
            task = scheduler.get_task(task_name)
            next_run = task.next_run.strftime("%Y-%m-%d %H:%M") if task and task.next_run else "unknown"
            return f"Enabled task **{task_name}**. Next run: {next_run}"
        return f"Error: Task '{task_name}' not found."

    # ------------------------------------------------------------------
    # DISABLE
    # ------------------------------------------------------------------
    elif action == "disable":
        task_name = args.get("task_name")
        if err := _enforce_user_scope(task_name):
            return err

        if scheduler.disable_task(task_name):
            return f"Disabled task **{task_name}**. It will not run until re-enabled."
        return f"Error: Task '{task_name}' not found."

    # ------------------------------------------------------------------
    # RUN_NOW
    # ------------------------------------------------------------------
    elif action == "run_now":
        task_name = args.get("task_name")
        if err := _enforce_user_scope(task_name):
            return err

        result = await scheduler.run_task_now(task_name)
        if result is None:
            # Could be not found or already running
            task = scheduler.get_task(task_name)
            if not task:
                return f"Error: Task '{task_name}' not found."
            return f"Task '{task_name}' is already running. Wait for it to finish."

        status = "succeeded" if result.success else "failed"
        parts = [f"Task **{task_name}** {status} ({result.duration_ms}ms)."]
        if result.output:
            parts.append(f"Output:\n```\n{result.output[:2000]}\n```")
        if result.error:
            parts.append(f"Error: {result.error}")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # RESULTS
    # ------------------------------------------------------------------
    elif action == "results":
        task_name = args.get("task_name")
        all_results = scheduler.get_results(limit=50)

        # Filter to user-scoped tasks
        results = [r for r in all_results if r.task_name.startswith(_USER_TASK_PREFIX)]
        # Optionally filter to a specific task
        if task_name:
            if err := _enforce_user_scope(task_name):
                return err
            results = [r for r in results if r.task_name == task_name]

        if not results:
            return "No execution results found."

        lines = []
        for r in results[:20]:
            status = "OK" if r.success else "FAIL"
            ts = r.timestamp.strftime("%Y-%m-%d %H:%M")
            line = f"- [{status}] **{r.task_name}** at {ts} ({r.duration_ms}ms)"
            if r.error:
                line += f" — {r.error[:80]}"
            elif r.output:
                line += f" — {r.output[:80]}"
            lines.append(line)

        return f"**Recent results ({len(results)} total, showing up to 20):**\n" + "\n".join(lines)

    # ------------------------------------------------------------------
    # STATS
    # ------------------------------------------------------------------
    elif action == "stats":
        stats = scheduler.get_stats()
        success_rate = (
            f"{stats['executions_successful'] / stats['executions_total'] * 100:.0f}%"
            if stats["executions_total"] > 0
            else "n/a"
        )
        return (
            f"**Scheduler stats:**\n"
            f"- Tasks: {stats['total_tasks']} total, {stats['enabled_tasks']} enabled, "
            f"{stats['running_tasks']} running now\n"
            f"- Executions: {stats['executions_total']} total — "
            f"{stats['executions_successful']} succeeded, "
            f"{stats['executions_failed']} failed (success rate: {success_rate})\n"
            f"- Scheduler running: {'yes' if stats['scheduler_running'] else 'no'}"
        )

    else:
        return f"Unknown action '{action}'. Valid: create, list, cancel, enable, disable, run_now, results, stats"


TOOLS = [
    ToolDef(
        name="manage_schedule",
        description=(
            "Create, list, cancel, enable, disable, and run scheduled tasks — "
            "reminders, recurring follow-ups, timed messages, and shell commands. "
            "Supports one-shot (delay), cron, and interval scheduling."
        ),
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "list", "cancel", "enable", "disable", "run_now", "results", "stats"],
                    "description": (
                        "What to do: create/list/cancel tasks, enable/disable them, "
                        "run one immediately, view execution results, or get stats"
                    ),
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
                "interval_minutes": {
                    "type": "integer",
                    "description": "Minutes between runs for interval tasks (e.g., 30 = every 30 minutes)",
                },
                "message": {
                    "type": "string",
                    "description": "Message to send when the task fires (requires channel_id)",
                },
                "command": {
                    "type": "string",
                    "description": "Shell command to run when the task fires (mutually exclusive with message)",
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory for shell commands (default: project root)",
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds for shell commands (default: 300)",
                },
                "channel_id": {
                    "type": "string",
                    "description": "Target channel ID for messages (defaults to current channel)",
                },
                "task_name": {
                    "type": "string",
                    "description": "Name of the task (for cancel, enable, disable, run_now, results)",
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
