"""Configuration management commands.

Provides commands for:
- Viewing configuration
- Editing configuration
- Validating configuration
- Managing profiles
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

config_app = typer.Typer(
    name="config",
    help="Configuration management",
    no_args_is_help=True,
)

console = Console()

# Default config locations
CONFIG_PATHS = [
    Path.home() / ".clara" / "config.yaml",
    Path.home() / ".clara" / "config.json",
    Path("clara.yaml"),
    Path("clara.json"),
]


def _find_config() -> Path | None:
    """Find the configuration file."""
    # Check environment variable first
    env_config = os.getenv("CLARA_CONFIG")
    if env_config:
        path = Path(env_config)
        if path.exists():
            return path

    # Check default locations
    for path in CONFIG_PATHS:
        if path.exists():
            return path

    return None


def _load_config(path: Path) -> dict:
    """Load configuration from file."""
    content = path.read_text()

    if path.suffix in (".yaml", ".yml"):
        import yaml
        return yaml.safe_load(content)
    else:
        return json.loads(content)


def _save_config(path: Path, config: dict) -> None:
    """Save configuration to file."""
    if path.suffix in (".yaml", ".yml"):
        import yaml
        content = yaml.dump(config, default_flow_style=False, sort_keys=False)
    else:
        content = json.dumps(config, indent=2)

    path.write_text(content)


@config_app.command("show")
def show_config(
    section: Optional[str] = typer.Argument(None, help="Configuration section to show"),
    raw: bool = typer.Option(False, "--raw", "-r", help="Show raw config without formatting"),
) -> None:
    """Show current configuration.

    Examples:
        clara config show              # Show all configuration
        clara config show llm          # Show LLM section
        clara config show discord      # Show Discord section
        clara config show --raw        # Show raw YAML/JSON
    """
    config_path = _find_config()

    if not config_path:
        console.print("[yellow]No configuration file found[/yellow]")
        console.print("Create one at ~/.clara/config.yaml or run 'clara onboard'")
        return

    try:
        config = _load_config(config_path)
    except Exception as e:
        console.print(f"[red]Failed to load config: {e}[/red]")
        raise typer.Exit(1)

    if section:
        if section not in config:
            console.print(f"[red]Section not found: {section}[/red]")
            console.print(f"Available sections: {', '.join(config.keys())}")
            raise typer.Exit(1)
        config = {section: config[section]}

    if raw:
        if config_path.suffix in (".yaml", ".yml"):
            import yaml
            content = yaml.dump(config, default_flow_style=False)
            syntax = Syntax(content, "yaml", theme="monokai")
        else:
            content = json.dumps(config, indent=2)
            syntax = Syntax(content, "json", theme="monokai")
        console.print(syntax)
    else:
        _print_config_tree(config)


def _print_config_tree(config: dict, prefix: str = "") -> None:
    """Print configuration as a tree."""
    for key, value in config.items():
        if isinstance(value, dict):
            console.print(f"{prefix}[bold cyan]{key}:[/bold cyan]")
            _print_config_tree(value, prefix + "  ")
        elif isinstance(value, list):
            console.print(f"{prefix}[bold cyan]{key}:[/bold cyan]")
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    console.print(f"{prefix}  [dim]- item {i}:[/dim]")
                    _print_config_tree(item, prefix + "    ")
                else:
                    console.print(f"{prefix}  [dim]- {item}[/dim]")
        else:
            # Mask sensitive values
            display_value = value
            if any(s in key.lower() for s in ["key", "token", "secret", "password"]):
                if value and len(str(value)) > 8:
                    display_value = str(value)[:4] + "..." + str(value)[-4:]

            console.print(f"{prefix}[cyan]{key}:[/cyan] {display_value}")


@config_app.command("validate")
def validate_config() -> None:
    """Validate configuration file.

    Checks for:
    - Valid YAML/JSON syntax
    - Required fields
    - Valid values
    - Environment variable references

    Examples:
        clara config validate
    """
    config_path = _find_config()

    if not config_path:
        console.print("[red]No configuration file found[/red]")
        raise typer.Exit(1)

    console.print(f"[blue]Validating {config_path}...[/blue]")

    errors = []
    warnings = []

    # Check syntax
    try:
        config = _load_config(config_path)
    except Exception as e:
        console.print(f"[red]Invalid syntax: {e}[/red]")
        raise typer.Exit(1)

    # Check required sections
    required_sections = ["llm"]
    for section in required_sections:
        if section not in config:
            errors.append(f"Missing required section: {section}")

    # Check LLM config
    if "llm" in config:
        llm = config["llm"]
        if "provider" not in llm:
            errors.append("llm.provider is required")
        elif llm["provider"] not in ["openrouter", "nanogpt", "openai", "anthropic"]:
            warnings.append(f"Unknown LLM provider: {llm['provider']}")

    # Check for unresolved environment variables
    def check_env_vars(obj, path=""):
        if isinstance(obj, str):
            if obj.startswith("${") and obj.endswith("}"):
                var_name = obj[2:-1]
                if not os.getenv(var_name):
                    warnings.append(f"Unset environment variable at {path}: {var_name}")
        elif isinstance(obj, dict):
            for k, v in obj.items():
                check_env_vars(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                check_env_vars(v, f"{path}[{i}]")

    check_env_vars(config)

    # Print results
    if errors:
        console.print("\n[red]Errors:[/red]")
        for error in errors:
            console.print(f"  [red]✗[/red] {error}")

    if warnings:
        console.print("\n[yellow]Warnings:[/yellow]")
        for warning in warnings:
            console.print(f"  [yellow]![/yellow] {warning}")

    if not errors and not warnings:
        console.print("[green]✓ Configuration is valid[/green]")
    elif not errors:
        console.print("\n[green]✓ Configuration is valid (with warnings)[/green]")
    else:
        raise typer.Exit(1)


@config_app.command("set")
def set_config(
    key: str = typer.Argument(..., help="Configuration key (dot notation)"),
    value: str = typer.Argument(..., help="Value to set"),
) -> None:
    """Set a configuration value.

    Use dot notation for nested keys.

    Examples:
        clara config set llm.provider anthropic
        clara config set llm.model claude-sonnet-4-5
        clara config set discord.prefix "!"
    """
    config_path = _find_config()

    if not config_path:
        # Create default config
        config_path = Path.home() / ".clara" / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config = {}
    else:
        config = _load_config(config_path)

    # Navigate to the key
    keys = key.split(".")
    current = config

    for k in keys[:-1]:
        if k not in current:
            current[k] = {}
        current = current[k]

    # Set the value (try to parse as JSON for complex types)
    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError:
        parsed_value = value

    current[keys[-1]] = parsed_value

    # Save
    _save_config(config_path, config)
    console.print(f"[green]Set {key} = {value}[/green]")


@config_app.command("unset")
def unset_config(
    key: str = typer.Argument(..., help="Configuration key to remove"),
) -> None:
    """Remove a configuration value.

    Examples:
        clara config unset discord.prefix
    """
    config_path = _find_config()

    if not config_path:
        console.print("[yellow]No configuration file found[/yellow]")
        return

    config = _load_config(config_path)

    # Navigate to the key
    keys = key.split(".")
    current = config

    for k in keys[:-1]:
        if k not in current:
            console.print(f"[yellow]Key not found: {key}[/yellow]")
            return
        current = current[k]

    if keys[-1] not in current:
        console.print(f"[yellow]Key not found: {key}[/yellow]")
        return

    del current[keys[-1]]

    # Save
    _save_config(config_path, config)
    console.print(f"[green]Removed {key}[/green]")


@config_app.command("edit")
def edit_config() -> None:
    """Open configuration file in editor.

    Uses $EDITOR or defaults to vim/nano.

    Examples:
        clara config edit
    """
    import subprocess

    config_path = _find_config()

    if not config_path:
        # Create default config
        config_path = Path.home() / ".clara" / "config.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text("# Clara Configuration\n\nllm:\n  provider: anthropic\n")

    editor = os.getenv("EDITOR", os.getenv("VISUAL", "vim"))

    try:
        subprocess.run([editor, str(config_path)])
    except FileNotFoundError:
        console.print(f"[red]Editor not found: {editor}[/red]")
        console.print("Set $EDITOR environment variable")
        raise typer.Exit(1)


@config_app.command("path")
def show_path() -> None:
    """Show configuration file path.

    Examples:
        clara config path
    """
    config_path = _find_config()

    if config_path:
        console.print(f"[green]{config_path}[/green]")
    else:
        console.print("[yellow]No configuration file found[/yellow]")
        console.print("\nSearched locations:")
        for path in CONFIG_PATHS:
            console.print(f"  - {path}")


@config_app.command("init")
def init_config(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing config"),
) -> None:
    """Initialize a new configuration file.

    Creates a default configuration at ~/.clara/config.yaml

    Examples:
        clara config init
        clara config init --force
    """
    config_path = Path.home() / ".clara" / "config.yaml"

    if config_path.exists() and not force:
        console.print(f"[yellow]Config already exists: {config_path}[/yellow]")
        console.print("Use --force to overwrite")
        return

    config_path.parent.mkdir(parents=True, exist_ok=True)

    default_config = """# Clara Configuration
# See documentation for all options

llm:
  provider: anthropic
  # api_key: ${ANTHROPIC_API_KEY}
  model: claude-sonnet-4-5

memory:
  enabled: true
  provider: mem0
  # For PostgreSQL: provider: postgres

gateway:
  host: 127.0.0.1
  port: 18789

# discord:
#   token: ${DISCORD_BOT_TOKEN}
#   allowed_servers: []
#   allowed_channels: []

# agents:
#   - name: clara
#     system_prompt: "You are Clara, a helpful AI assistant."
#     tier: mid
"""

    config_path.write_text(default_config)
    console.print(f"[green]Created configuration at {config_path}[/green]")
    console.print("Edit with: clara config edit")
