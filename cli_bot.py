#!/usr/bin/env python3
"""Clara CLI - Terminal interface for Clara AI assistant.

Usage:
    poetry run python cli_bot.py

Commands:
    Ctrl+C  - Cancel current input
    Ctrl+D  - Exit
    !high   - Use high-tier model for next message
    !mid    - Use mid-tier model (default)
    !low    - Use low-tier model
"""

from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.status import Status

from adapters.cli import CLIAdapter
from adapters.cli.logging import configure_cli_logging
from clara_core import (
    MemoryManager,
    get_config,
    get_version,
    init_platform,
    make_llm_streaming,
)
from db.connection import SessionLocal


async def generate_response(
    mm: MemoryManager,
    console: Console,
    user_id: str,
    context_id: str,
    project_id: str,
    user_message: str,
    tier_override: str | None = None,
) -> str:
    """Generate a streaming response from Clara.

    Args:
        mm: The MemoryManager instance
        console: Rich Console for output
        user_id: User identifier
        context_id: Context identifier (e.g., "cli-default")
        project_id: Project identifier
        user_message: The user's input message
        tier_override: Optional model tier override ("high", "mid", "low")

    Returns:
        The complete assistant response
    """
    loop = asyncio.get_event_loop()

    # Fetch memories (blocking, run in executor)
    user_mems, proj_mems = await loop.run_in_executor(
        None,
        lambda: mm.fetch_mem0_context(user_id, project_id, user_message, is_dm=True),
    )

    # Get session and recent messages
    db = SessionLocal()
    try:
        session = mm.get_or_create_session(db, user_id, context_id, project_id)
        recent_msgs = mm.get_recent_messages(db, session.id)
        session_summary = session.session_summary if hasattr(session, "session_summary") else None
    finally:
        db.close()

    # Fetch emotional context for tone calibration
    emotional_context = await loop.run_in_executor(
        None,
        lambda: mm.fetch_emotional_context(user_id, limit=3),
    )

    # Fetch recurring topic patterns
    recurring_topics = await loop.run_in_executor(
        None,
        lambda: mm.fetch_topic_recurrence(user_id, lookback_days=14, min_mentions=2),
    )

    # Build prompt with Clara's persona
    prompt_messages = mm.build_prompt(
        user_mems,
        proj_mems,
        session_summary,
        recent_msgs,
        user_message,
        emotional_context=emotional_context,
        recurring_topics=recurring_topics,
    )

    # Get streaming LLM
    llm_stream = make_llm_streaming(tier=tier_override)

    # Show subtle spinner while thinking
    console.print()
    console.print("[bold]Clara:[/bold]")

    accumulated = ""

    # Brief spinner before streaming starts
    with Status(
        "[dim]thinking...[/dim]",
        console=console,
        spinner="dots",
        spinner_style="dim",
    ):
        # Initialize the stream (first chunk triggers spinner to stop)
        stream_iter = iter(llm_stream(prompt_messages))
        try:
            first_chunk = next(stream_iter)
            accumulated += first_chunk
        except StopIteration:
            pass

    # Now stream the response with Live
    with Live(Markdown(accumulated), console=console, refresh_per_second=10, transient=False) as live:
        for chunk in stream_iter:
            accumulated += chunk
            live.update(Markdown(accumulated))

    console.print()  # Spacing after response
    return accumulated


async def store_exchange(
    mm: MemoryManager,
    user_id: str,
    context_id: str,
    project_id: str,
    user_message: str,
    assistant_response: str,
) -> None:
    """Store the exchange in Clara's memory system.

    Args:
        mm: The MemoryManager instance
        user_id: User identifier
        context_id: Context identifier
        project_id: Project identifier
        user_message: The user's input message
        assistant_response: Clara's response
    """
    loop = asyncio.get_event_loop()

    db = SessionLocal()
    try:
        session = mm.get_or_create_session(db, user_id, context_id, project_id)

        # Store user message
        mm.store_message(db, session.id, user_id, "user", user_message)

        # Store assistant response
        mm.store_message(db, session.id, user_id, "assistant", assistant_response)

        db.commit()

        # Get recent messages for memory extraction
        recent_msgs = mm.get_recent_messages(db, session.id)
    finally:
        db.close()

    # Extract memories async (run in executor)
    await loop.run_in_executor(
        None,
        lambda: mm.add_to_mem0(
            user_id, project_id, recent_msgs, user_message, assistant_response, is_dm=True
        ),
    )


def parse_tier_prefix(content: str) -> tuple[str | None, str]:
    """Parse tier prefix from user input.

    Args:
        content: The raw user input

    Returns:
        Tuple of (tier_override or None, cleaned content)
    """
    content = content.strip()
    tier_prefixes = {
        "!high ": "high",
        "!opus ": "high",
        "!mid ": "mid",
        "!sonnet ": "mid",
        "!low ": "low",
        "!haiku ": "low",
        "!fast ": "low",
    }

    for prefix, tier in tier_prefixes.items():
        if content.lower().startswith(prefix):
            return tier, content[len(prefix) :]

    return None, content


async def main() -> None:
    """Main CLI entry point."""
    # Configure logging FIRST - before any other imports that trigger logging
    log_file = configure_cli_logging()

    # Load environment
    load_dotenv(override=True)

    # Initialize platform
    init_platform()

    # Get singletons
    mm = MemoryManager.get_instance()
    config = get_config()

    # Create adapter
    adapter = CLIAdapter()
    console = adapter.console

    # Set up prompt session with history
    history_path = os.path.expanduser("~/.clara_cli_history")
    session = PromptSession(history=FileHistory(history_path))

    # User identity - prefix with "cli-" to distinguish from Discord users
    user_id = f"cli-{config.user_id}"
    context_id = "cli-default"
    project_id = config.default_project

    # Welcome message
    console.print(f"[bold blue]Clara CLI v{get_version()}[/bold blue]")
    console.print(f"User: {user_id}")
    console.print(f"Logs: {log_file}")
    console.print("Type your message. Ctrl+C to cancel, Ctrl+D to exit.")
    console.print("Model prefixes: !high, !mid, !low")
    console.print()

    # REPL loop
    while True:
        try:
            user_input = await session.prompt_async("You: ")
            if not user_input.strip():
                continue

            # Parse tier prefix
            tier_override, content = parse_tier_prefix(user_input)

            if not content.strip():
                continue

            # Generate response
            response = await generate_response(
                mm, console, user_id, context_id, project_id, content, tier_override
            )

            # Store exchange in memory
            if response:
                await store_exchange(
                    mm, user_id, context_id, project_id, content, response
                )

        except KeyboardInterrupt:
            console.print("\n[dim]Cancelled[/dim]")
            continue
        except EOFError:
            console.print("\n[blue]Goodbye![/blue]")
            break
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            continue


if __name__ == "__main__":
    asyncio.run(main())
