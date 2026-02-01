"""Doctor command implementation.

Runs comprehensive system diagnostics and health checks.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def run_doctor() -> None:
    """Run system diagnostics."""
    console.print(Panel(
        "[bold blue]Clara System Diagnostics[/bold blue]\n\n"
        "Running health checks...",
        title="Doctor",
        border_style="blue",
    ))

    checks: list[tuple[str, Callable[[], tuple[bool, str]]]] = [
        ("Python Version", _check_python),
        ("Configuration", _check_config),
        ("Database", _check_database),
        ("Memory System", _check_memory),
        ("LLM Provider", _check_llm),
        ("Gateway", _check_gateway),
        ("Discord", _check_discord),
        ("Dependencies", _check_dependencies),
    ]

    results = []
    passed = 0
    failed = 0
    warnings = 0

    for name, check_fn in checks:
        console.print(f"[dim]Checking {name}...[/dim]", end=" ")
        try:
            success, message = check_fn()
            if success:
                if "warning" in message.lower():
                    results.append((name, "⚠️", message, "yellow"))
                    warnings += 1
                else:
                    results.append((name, "✓", message, "green"))
                    passed += 1
            else:
                results.append((name, "✗", message, "red"))
                failed += 1
        except Exception as e:
            results.append((name, "✗", f"Error: {e}", "red"))
            failed += 1
        console.print("[dim]done[/dim]")

    # Display results
    console.print()
    table = Table(title="Diagnostic Results")
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Details", style="dim")

    for name, status, message, color in results:
        table.add_row(name, f"[{color}]{status}[/{color}]", message)

    console.print(table)

    # Summary
    console.print()
    if failed == 0:
        if warnings > 0:
            console.print(f"[yellow]All checks passed with {warnings} warning(s)[/yellow]")
        else:
            console.print("[green]All checks passed! Clara is healthy.[/green]")
    else:
        console.print(f"[red]{failed} check(s) failed. Please fix the issues above.[/red]")
        if warnings > 0:
            console.print(f"[yellow]Additionally, {warnings} warning(s) found.[/yellow]")

    # Recommendations
    if failed > 0:
        console.print("\n[bold]Recommendations:[/bold]")
        for name, status, message, color in results:
            if status == "✗":
                _print_recommendation(name, message)


def _check_python() -> tuple[bool, str]:
    """Check Python version."""
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"

    if version.major < 3:
        return False, f"Python 3.11+ required, got {version_str}"

    if version.minor < 11:
        return False, f"Python 3.11+ required, got {version_str}"

    if version.minor >= 14:
        return True, f"{version_str} (warning: untested version)"

    return True, version_str


def _check_config() -> tuple[bool, str]:
    """Check configuration."""
    config_paths = [
        Path.home() / ".clara" / "config.yaml",
        Path.home() / ".clara" / "config.json",
        Path("clara.yaml"),
        Path("clara.json"),
    ]

    env_config = os.getenv("CLARA_CONFIG")
    if env_config:
        path = Path(env_config)
        if path.exists():
            return True, f"Found at {path}"
        return False, f"CLARA_CONFIG set but file not found: {path}"

    for path in config_paths:
        if path.exists():
            return True, f"Found at {path}"

    # Check for essential env vars as fallback
    if os.getenv("LLM_PROVIDER") or os.getenv("OPENROUTER_API_KEY"):
        return True, "Using environment variables (no config file)"

    return False, "No configuration found. Run 'clara onboard' to set up."


def _check_database() -> tuple[bool, str]:
    """Check database connectivity."""
    db_url = os.getenv("DATABASE_URL")

    if db_url:
        if "postgresql" in db_url:
            try:
                import sqlalchemy
                engine = sqlalchemy.create_engine(db_url)
                with engine.connect() as conn:
                    conn.execute(sqlalchemy.text("SELECT 1"))
                return True, "PostgreSQL connected"
            except Exception as e:
                return False, f"PostgreSQL connection failed: {e}"
        return True, "Database URL configured"

    # Check SQLite
    sqlite_path = Path("clara.db")
    if sqlite_path.exists():
        return True, f"SQLite at {sqlite_path}"

    return True, "Will use SQLite (default)"


def _check_memory() -> tuple[bool, str]:
    """Check memory system."""
    # Check OpenAI key for embeddings
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        return False, "OPENAI_API_KEY required for embeddings"

    # Check vector store
    mem_url = os.getenv("MEM0_DATABASE_URL")
    if mem_url:
        if "postgresql" in mem_url:
            try:
                import sqlalchemy
                engine = sqlalchemy.create_engine(mem_url)
                with engine.connect() as conn:
                    # Check for pgvector extension
                    result = conn.execute(sqlalchemy.text(
                        "SELECT 1 FROM pg_extension WHERE extname = 'vector'"
                    ))
                    if result.fetchone():
                        return True, "PostgreSQL (pgvector)"
                    return False, "pgvector extension not installed"
            except Exception as e:
                return False, f"Memory DB connection failed: {e}"

    # Check Qdrant
    qdrant_url = os.getenv("QDRANT_URL")
    if qdrant_url:
        try:
            import httpx
            response = httpx.get(f"{qdrant_url}/healthz", timeout=5)
            if response.status_code == 200:
                return True, f"Qdrant at {qdrant_url}"
            return False, f"Qdrant unhealthy: {response.status_code}"
        except Exception:
            return False, f"Cannot connect to Qdrant at {qdrant_url}"

    # Local Qdrant
    qdrant_path = Path(".qdrant")
    if qdrant_path.exists():
        return True, "Local Qdrant storage"

    return True, "Will use default Qdrant storage"


def _check_llm() -> tuple[bool, str]:
    """Check LLM provider."""
    provider = os.getenv("LLM_PROVIDER", "openrouter")

    key_map = {
        "openrouter": ("OPENROUTER_API_KEY", "OpenRouter"),
        "anthropic": ("ANTHROPIC_API_KEY", "Anthropic"),
        "openai": ("CUSTOM_OPENAI_API_KEY", "OpenAI"),
        "nanogpt": ("NANOGPT_API_KEY", "NanoGPT"),
    }

    if provider not in key_map:
        return False, f"Unknown provider: {provider}"

    key_env, name = key_map[provider]
    key = os.getenv(key_env)

    if not key:
        return False, f"{key_env} not set"

    # Try a simple API call
    model = os.getenv(f"{provider.upper()}_MODEL", "default")
    return True, f"{name} ({model[:30]})"


def _check_gateway() -> tuple[bool, str]:
    """Check gateway status."""
    pid_file = Path.home() / ".clara" / "gateway.pid"

    if not pid_file.exists():
        return True, "Not running (optional)"

    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)

        # Try to connect
        gateway_url = os.getenv("CLARA_GATEWAY_URL", "ws://127.0.0.1:18789")
        try:
            import json

            import websockets.sync.client as ws_client

            with ws_client.connect(gateway_url, close_timeout=2) as ws:
                ws.send(json.dumps({"type": "ping"}))
                response = json.loads(ws.recv())
                if response.get("type") == "pong":
                    return True, f"Running (PID {pid})"
        except Exception:
            return True, f"Running (PID {pid}, no WebSocket)"

        return True, f"Running (PID {pid})"
    except (ValueError, ProcessLookupError, PermissionError):
        return True, "PID file stale (warning: cleanup needed)"


def _check_discord() -> tuple[bool, str]:
    """Check Discord configuration."""
    token = os.getenv("DISCORD_BOT_TOKEN")

    if not token:
        return True, "Not configured (optional)"

    # Validate token format (rough check)
    if len(token) < 50:
        return False, "Token appears invalid (too short)"

    # Check for additional config
    servers = os.getenv("DISCORD_ALLOWED_SERVERS")
    channels = os.getenv("DISCORD_ALLOWED_CHANNELS")

    config_parts = []
    if servers:
        config_parts.append(f"{len(servers.split(','))} servers")
    if channels:
        config_parts.append(f"{len(channels.split(','))} channels")

    if config_parts:
        return True, f"Configured ({', '.join(config_parts)})"

    return True, "Configured (all servers/channels)"


def _check_dependencies() -> tuple[bool, str]:
    """Check required dependencies."""
    required = [
        "typer",
        "rich",
        "pydantic",
    ]

    optional = [
        ("websockets", "Gateway/real-time"),
        ("discord.py", "Discord integration"),
        ("mem0ai", "Memory system"),
        ("openai", "OpenAI/embeddings"),
        ("anthropic", "Anthropic provider"),
    ]

    missing_required = []
    missing_optional = []

    for pkg in required:
        try:
            __import__(pkg.replace("-", "_").replace(".", "_"))
        except ImportError:
            missing_required.append(pkg)

    for pkg, desc in optional:
        try:
            __import__(pkg.replace("-", "_").replace(".", "_"))
        except ImportError:
            missing_optional.append(f"{pkg} ({desc})")

    if missing_required:
        return False, f"Missing: {', '.join(missing_required)}"

    if missing_optional:
        return True, f"OK (optional missing: {len(missing_optional)})"

    return True, "All dependencies installed"


def _print_recommendation(check_name: str, message: str) -> None:
    """Print recommendation for a failed check."""
    recommendations = {
        "Python Version": "Install Python 3.11+ from python.org or use pyenv",
        "Configuration": "Run 'clara onboard' to set up configuration",
        "Database": "Check DATABASE_URL or ensure SQLite is writable",
        "Memory System": "Set OPENAI_API_KEY for embeddings, check vector store",
        "LLM Provider": "Set your LLM provider API key (see documentation)",
        "Gateway": "If needed, start with 'clara serve'",
        "Discord": "Check DISCORD_BOT_TOKEN configuration",
        "Dependencies": "Run 'pip install -e .' or 'poetry install'",
    }

    rec = recommendations.get(check_name, "Check the documentation for setup instructions")
    console.print(f"  [cyan]{check_name}:[/cyan] {rec}")
