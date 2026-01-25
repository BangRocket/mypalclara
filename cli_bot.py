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

# Configure logging FIRST - before any imports that trigger logging
# This must happen before clara_core imports, which load mem0 at module level
from adapters.cli.logging import configure_cli_logging

_LOG_FILE = configure_cli_logging()

from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.status import Status

from adapters.cli import CLIAdapter
from clara_core import (
    MemoryManager,
    get_config,
    get_version,
    init_platform,
    make_llm_streaming,
    make_llm_with_tools,
    make_llm_with_tools_anthropic,
)
from clara_core.mcp import get_mcp_manager, init_mcp
from db.connection import SessionLocal
from tools import ToolContext, get_registry, init_tools


async def generate_response(
    mm: MemoryManager,
    console: Console,
    session: PromptSession,
    user_id: str,
    context_id: str,
    project_id: str,
    user_message: str,
    tier_override: str | None = None,
) -> str:
    """Generate a streaming response from Clara with tool execution support.

    Args:
        mm: The MemoryManager instance
        console: Rich Console for output
        session: PromptSession for interactive approvals
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
        db_session = mm.get_or_create_session(db, user_id, context_id, project_id)
        recent_msgs = mm.get_recent_messages(db, db_session.id)
        session_summary = db_session.session_summary if hasattr(db_session, "session_summary") else None
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

    # Get available tools
    tools = get_cli_tools()

    # Check if we have tools - use tool-enabled LLM if so
    if tools:
        return await _generate_with_tools(
            console, session, user_id, prompt_messages, tools, tier_override
        )
    else:
        # No tools, use streaming response
        return await _generate_streaming(console, prompt_messages, tier_override)


async def _generate_streaming(
    console: Console,
    messages: list[dict],
    tier_override: str | None = None,
) -> str:
    """Generate a streaming response without tools.

    Args:
        console: Rich Console for output
        messages: Prompt messages
        tier_override: Optional tier override

    Returns:
        Complete assistant response
    """
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
        stream_iter = iter(llm_stream(messages))
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


async def _generate_with_tools(
    console: Console,
    session: PromptSession,
    user_id: str,
    messages: list[dict],
    tools: list[dict],
    tier_override: str | None = None,
) -> str:
    """Generate a response with tool execution loop.

    Args:
        console: Rich Console for output
        session: PromptSession for interactive approvals
        user_id: User identifier
        messages: Prompt messages (modified in place)
        tools: Available tools in OpenAI format
        tier_override: Optional tier override

    Returns:
        Final assistant response
    """
    # Check which provider to use
    provider = os.getenv("LLM_PROVIDER", "openrouter").lower()

    # Use native Anthropic SDK for anthropic provider (better tool support)
    if provider == "anthropic":
        return await _generate_with_tools_anthropic(
            console, session, user_id, messages, tools, tier_override
        )

    # OpenAI-compatible providers
    llm_call = make_llm_with_tools(tools=tools, tier=tier_override)

    # Create tool context
    tool_context = make_tool_context(user_id, console, session)
    registry = get_registry()

    # Tool execution loop (max 10 iterations to prevent infinite loops)
    max_iterations = 10
    iteration = 0

    console.print()
    console.print("[bold]Clara:[/bold]")

    while iteration < max_iterations:
        iteration += 1

        # Show thinking spinner
        with Status(
            "[dim]thinking...[/dim]" if iteration == 1 else "[dim]processing...[/dim]",
            console=console,
            spinner="dots",
            spinner_style="dim",
        ):
            response = llm_call(messages)

        # Check for tool calls
        if not response.choices or not response.choices[0].message.tool_calls:
            # No tool calls - final response
            final_content = response.choices[0].message.content or ""
            console.print(Markdown(final_content))
            console.print()
            return final_content

        # Extract tool calls
        assistant_message = response.choices[0].message
        tool_calls = assistant_message.tool_calls

        # Add assistant message with tool calls to history
        messages.append(
            {
                "role": "assistant",
                "content": assistant_message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in tool_calls
                ],
            }
        )

        # Execute each tool call
        for idx, tool_call in enumerate(tool_calls, 1):
            tool_name = tool_call.function.name
            try:
                import json

                arguments = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                arguments = {}

            # Show which tool is being used
            console.print(f"[dim]🛠  Using {tool_name}... (step {idx})[/dim]")

            # Execute tool
            try:
                result = await registry.execute(tool_name, arguments, tool_context)
            except Exception as e:
                result = f"Error: {str(e)}"

            # Add tool result to messages
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

    # Max iterations reached
    console.print(
        "[yellow]Warning: Maximum tool execution iterations reached. Returning last result.[/yellow]"
    )
    console.print()
    return "I encountered too many tool calls and had to stop. Please try rephrasing your request."


async def _generate_with_tools_anthropic(
    console: Console,
    session: PromptSession,
    user_id: str,
    messages: list[dict],
    tools: list[dict],
    tier_override: str | None = None,
) -> str:
    """Generate a response with tool execution using native Anthropic SDK.

    This provides better tool calling support for Claude proxies like clewdr.

    Args:
        console: Rich Console for output
        session: PromptSession for interactive approvals
        user_id: User identifier
        messages: Prompt messages (modified in place)
        tools: Available tools in OpenAI format
        tier_override: Optional tier override

    Returns:
        Final assistant response
    """
    import json

    # Get native Anthropic LLM with tool support
    llm_call = make_llm_with_tools_anthropic(tools=tools, tier=tier_override)

    # Create tool context
    tool_context = make_tool_context(user_id, console, session)
    registry = get_registry()

    # Tool execution loop (max 10 iterations to prevent infinite loops)
    max_iterations = 10
    iteration = 0

    console.print()
    console.print("[bold]Clara:[/bold]")

    while iteration < max_iterations:
        iteration += 1

        # Show thinking spinner
        with Status(
            "[dim]thinking...[/dim]" if iteration == 1 else "[dim]processing...[/dim]",
            console=console,
            spinner="dots",
            spinner_style="dim",
        ):
            response = llm_call(messages)

        # Anthropic returns content as a list of blocks
        # Check stop_reason for tool_use
        if response.stop_reason != "tool_use":
            # Extract text content from response
            final_content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_content += block.text
            console.print(Markdown(final_content))
            console.print()
            return final_content

        # Extract tool use blocks and text content
        text_content = ""
        tool_uses = []
        for block in response.content:
            if hasattr(block, "text"):
                text_content += block.text
            elif block.type == "tool_use":
                tool_uses.append(block)

        if not tool_uses:
            # No tool uses found despite stop_reason - return what we have
            console.print(Markdown(text_content))
            console.print()
            return text_content

        # Build assistant message in OpenAI format (converter will handle it)
        # This ensures _convert_message_to_anthropic properly converts to Anthropic format
        messages.append({
            "role": "assistant",
            "content": text_content or "",
            "tool_calls": [
                {
                    "id": tu.id,
                    "type": "function",
                    "function": {"name": tu.name, "arguments": json.dumps(tu.input)},
                }
                for tu in tool_uses
            ],
        })

        # Execute each tool call and add results in OpenAI format
        for idx, tool_use in enumerate(tool_uses, 1):
            tool_name = tool_use.name
            arguments = tool_use.input if isinstance(tool_use.input, dict) else {}

            # Show which tool is being used
            console.print(f"[dim]🛠  Using {tool_name}... (step {idx})[/dim]")

            # Execute tool
            try:
                result = await registry.execute(tool_name, arguments, tool_context)
            except Exception as e:
                result = f"Error: {str(e)}"

            # Add tool result in OpenAI format (converter will handle it)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_use.id,
                "content": result,
            })

    # Max iterations reached
    console.print(
        "[yellow]Warning: Maximum tool execution iterations reached. Returning last result.[/yellow]"
    )
    console.print()
    return "I encountered too many tool calls and had to stop. Please try rephrasing your request."


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


def get_cli_tools() -> list[dict]:
    """Get all available tools for CLI (native + MCP).

    Returns:
        List of tool definitions in OpenAI format
    """
    # Get native tools from registry
    registry = get_registry()
    native_tools = registry.get_tools(platform="cli", format="openai")

    # Get MCP tools if available
    mcp_manager = get_mcp_manager()
    mcp_tools = []
    if mcp_manager:
        try:
            mcp_tools = mcp_manager.get_tools_openai_format()
        except Exception as e:
            print(f"[CLI] Warning: Failed to get MCP tools: {e}")

    return native_tools + mcp_tools


def make_tool_context(
    user_id: str,
    console: Console,
    session: PromptSession,
) -> ToolContext:
    """Create a ToolContext for CLI tool execution.

    Args:
        user_id: User identifier
        console: Rich Console instance
        session: PromptSession for interactive approval

    Returns:
        ToolContext with CLI-specific extras
    """
    return ToolContext(
        user_id=user_id,
        channel_id="cli-terminal",
        platform="cli",
        extra={
            "console": console,
            "session": session,
            "shell_cwd": os.getcwd(),
            "shell_env": {},
        },
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
    # Logging already configured at module load (before imports)
    log_file = _LOG_FILE

    # Load environment
    load_dotenv(override=True)

    # Initialize platform
    init_platform()

    # Initialize tools and MCP
    await init_tools(hot_reload=False)
    await init_mcp()

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
                mm, console, session, user_id, context_id, project_id, content, tier_override
            )

            # Store exchange in memory (run in background to not block prompt)
            if response:
                asyncio.create_task(
                    store_exchange(mm, user_id, context_id, project_id, content, response)
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
