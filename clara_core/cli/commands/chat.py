"""Chat command implementation.

Provides interactive chat with Clara via the CLI.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()


def run_chat(
    message: Optional[str] = None,
    agent: str = "clara",
    tier: str = "mid",
) -> None:
    """Run chat session.

    Args:
        message: Single message to send (interactive if None)
        agent: Agent/persona to use
        tier: Model tier (low, mid, high)
    """
    if message:
        # Single message mode
        _send_single_message(message, agent, tier)
    else:
        # Interactive mode
        _run_interactive_chat(agent, tier)


def _send_single_message(message: str, agent: str, tier: str) -> None:
    """Send a single message and print the response."""
    console.print(f"[dim]Sending to {agent} ({tier} tier)...[/dim]\n")

    try:
        response = asyncio.run(_get_response(message, agent, tier))
        console.print(Markdown(response))
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def _run_interactive_chat(agent: str, tier: str) -> None:
    """Run interactive chat session."""
    console.print(Panel(
        f"[bold blue]Clara Chat[/bold blue]\n\n"
        f"Agent: [green]{agent}[/green]\n"
        f"Tier: [green]{tier}[/green]\n\n"
        f"Type [bold]quit[/bold] or [bold]exit[/bold] to end the session.\n"
        f"Type [bold]/tier <level>[/bold] to change tier.\n"
        f"Type [bold]/agent <name>[/bold] to change agent.",
        title="Interactive Chat",
        border_style="blue",
    ))

    current_tier = tier
    current_agent = agent
    history: list[dict] = []

    while True:
        try:
            # Get user input
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")

            if not user_input.strip():
                continue

            # Handle special commands
            lower_input = user_input.lower().strip()

            if lower_input in ("quit", "exit", "/quit", "/exit"):
                console.print("[dim]Goodbye![/dim]")
                break

            if lower_input.startswith("/tier "):
                new_tier = lower_input.split(" ", 1)[1].strip()
                if new_tier in ("low", "mid", "high"):
                    current_tier = new_tier
                    console.print(f"[green]Tier set to {current_tier}[/green]")
                else:
                    console.print("[yellow]Valid tiers: low, mid, high[/yellow]")
                continue

            if lower_input.startswith("/agent "):
                current_agent = lower_input.split(" ", 1)[1].strip()
                console.print(f"[green]Agent set to {current_agent}[/green]")
                history = []  # Clear history on agent change
                continue

            if lower_input == "/clear":
                history = []
                console.print("[green]History cleared[/green]")
                continue

            if lower_input == "/history":
                if not history:
                    console.print("[dim]No history[/dim]")
                else:
                    for i, msg in enumerate(history[-10:]):
                        role = msg["role"]
                        content = msg["content"][:50] + "..." if len(msg["content"]) > 50 else msg["content"]
                        console.print(f"[dim]{i+1}. {role}: {content}[/dim]")
                continue

            if lower_input == "/help":
                console.print("""
[bold]Available commands:[/bold]
  /tier <low|mid|high>  - Change model tier
  /agent <name>         - Change agent/persona
  /clear                - Clear conversation history
  /history              - Show recent history
  /help                 - Show this help
  quit, exit            - End session
""")
                continue

            # Add to history
            history.append({"role": "user", "content": user_input})

            # Get response with streaming
            console.print()
            console.print("[bold green]Clara[/bold green]")

            try:
                response = asyncio.run(_get_streaming_response(
                    user_input,
                    current_agent,
                    current_tier,
                    history[:-1],  # Pass history without current message
                ))

                # Add response to history
                history.append({"role": "assistant", "content": response})

            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                history.pop()  # Remove failed message from history

        except KeyboardInterrupt:
            console.print("\n[dim]Use 'quit' to exit[/dim]")
        except EOFError:
            console.print("\n[dim]Goodbye![/dim]")
            break


async def _get_response(message: str, agent: str, tier: str) -> str:
    """Get a response from the LLM."""
    # Try to use the gateway if available
    gateway_url = os.getenv("CLARA_GATEWAY_URL")
    if gateway_url:
        return await _get_gateway_response(message, agent, tier, gateway_url)

    # Fall back to direct LLM call
    return await _get_direct_response(message, agent, tier)


async def _get_streaming_response(
    message: str,
    agent: str,
    tier: str,
    history: list[dict],
) -> str:
    """Get a streaming response from the LLM."""
    # Try to use the gateway if available
    gateway_url = os.getenv("CLARA_GATEWAY_URL")
    if gateway_url:
        return await _get_gateway_streaming_response(message, agent, tier, history, gateway_url)

    # Fall back to direct LLM call
    return await _get_direct_streaming_response(message, agent, tier, history)


async def _get_gateway_response(
    message: str,
    agent: str,
    tier: str,
    gateway_url: str,
) -> str:
    """Get response via gateway."""
    import json
    import uuid

    try:
        import websockets
    except ImportError:
        console.print("[yellow]websockets not installed, using direct mode[/yellow]")
        return await _get_direct_response(message, agent, tier)

    async with websockets.connect(gateway_url) as ws:
        # Send message
        request = {
            "type": "chat",
            "request_id": str(uuid.uuid4()),
            "user_id": os.getenv("USER_ID", "cli-user"),
            "channel": "cli",
            "message": message,
            "agent": agent,
            "tier": tier,
        }
        await ws.send(json.dumps(request))

        # Collect response
        response_text = ""
        while True:
            raw = await ws.recv()
            data = json.loads(raw)

            if data.get("type") == "chunk":
                response_text += data.get("content", "")
            elif data.get("type") == "complete":
                break
            elif data.get("type") == "error":
                raise Exception(data.get("error", "Unknown error"))

        return response_text


async def _get_gateway_streaming_response(
    message: str,
    agent: str,
    tier: str,
    history: list[dict],
    gateway_url: str,
) -> str:
    """Get streaming response via gateway."""
    import json
    import uuid

    try:
        import websockets
    except ImportError:
        console.print("[yellow]websockets not installed, using direct mode[/yellow]")
        return await _get_direct_streaming_response(message, agent, tier, history)

    async with websockets.connect(gateway_url) as ws:
        # Send message
        request = {
            "type": "chat",
            "request_id": str(uuid.uuid4()),
            "user_id": os.getenv("USER_ID", "cli-user"),
            "channel": "cli",
            "message": message,
            "agent": agent,
            "tier": tier,
            "history": history,
        }
        await ws.send(json.dumps(request))

        # Stream response
        response_text = ""
        with Live(console=console, refresh_per_second=10) as live:
            while True:
                raw = await ws.recv()
                data = json.loads(raw)

                if data.get("type") == "chunk":
                    chunk = data.get("content", "")
                    response_text += chunk
                    live.update(Markdown(response_text))
                elif data.get("type") == "complete":
                    break
                elif data.get("type") == "error":
                    raise Exception(data.get("error", "Unknown error"))

        return response_text


async def _get_direct_response(message: str, agent: str, tier: str) -> str:
    """Get response directly from LLM backend."""
    try:
        from llm_backends import get_llm_response
    except ImportError:
        return _get_fallback_response()

    # Build simple prompt
    system_prompt = _get_system_prompt(agent)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message},
    ]

    return await get_llm_response(messages, tier=tier)


async def _get_direct_streaming_response(
    message: str,
    agent: str,
    tier: str,
    history: list[dict],
) -> str:
    """Get streaming response directly from LLM backend."""
    try:
        from llm_backends import get_streaming_llm_response
    except ImportError:
        console.print(_get_fallback_response())
        return _get_fallback_response()

    # Build messages
    system_prompt = _get_system_prompt(agent)

    messages = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": message},
    ]

    # Stream response
    response_text = ""
    with Live(console=console, refresh_per_second=10) as live:
        async for chunk in get_streaming_llm_response(messages, tier=tier):
            response_text += chunk
            live.update(Markdown(response_text))

    return response_text


def _get_system_prompt(agent: str) -> str:
    """Get system prompt for agent."""
    # Default Clara prompt
    if agent.lower() == "clara":
        return """You are Clara, a friendly and helpful AI assistant.
You are knowledgeable, thoughtful, and always aim to be genuinely helpful.
You have a warm personality but remain professional and focused.
When you don't know something, you say so honestly."""

    # For other agents, use a generic prompt
    return f"You are {agent}, an AI assistant. Be helpful and informative."


def _get_fallback_response() -> str:
    """Fallback response when LLM is not available."""
    return """I'm sorry, but I couldn't connect to any LLM backend.

Please check:
1. Your LLM_PROVIDER environment variable is set
2. The corresponding API key is configured
3. The gateway is running (if using gateway mode)

Run `clara doctor` to diagnose the issue."""
