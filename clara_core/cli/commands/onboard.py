"""Onboard command implementation.

Interactive setup wizard for new Clara installations.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

console = Console()


def run_onboard() -> None:
    """Run the interactive onboarding wizard."""
    console.print(Panel(
        "[bold blue]Welcome to Clara![/bold blue]\n\n"
        "This wizard will help you set up Clara for the first time.\n\n"
        "You can press [bold]Ctrl+C[/bold] at any time to cancel.",
        title="Onboarding Wizard",
        border_style="blue",
    ))

    config = {}

    try:
        # Step 1: LLM Provider
        config["llm"] = _setup_llm_provider()

        # Step 2: Memory System
        config["memory"] = _setup_memory()

        # Step 3: Channels (Discord, etc.)
        config["channels"] = _setup_channels()

        # Step 4: Gateway settings
        config["gateway"] = _setup_gateway()

        # Save configuration
        _save_config(config)

        console.print(Panel(
            "[bold green]Setup Complete![/bold green]\n\n"
            "Your configuration has been saved to ~/.clara/config.yaml\n\n"
            "Next steps:\n"
            "  [cyan]clara doctor[/cyan]    - Verify your setup\n"
            "  [cyan]clara chat[/cyan]      - Start chatting\n"
            "  [cyan]clara serve[/cyan]     - Start the gateway",
            title="Success",
            border_style="green",
        ))

    except KeyboardInterrupt:
        console.print("\n[yellow]Setup cancelled[/yellow]")


def _setup_llm_provider() -> dict:
    """Configure LLM provider."""
    console.print("\n[bold]Step 1: LLM Provider[/bold]\n")

    providers = {
        "1": ("anthropic", "Anthropic Claude (recommended)"),
        "2": ("openrouter", "OpenRouter (multiple models)"),
        "3": ("openai", "OpenAI / Custom endpoint"),
        "4": ("nanogpt", "NanoGPT"),
    }

    console.print("Choose your LLM provider:")
    for key, (_, name) in providers.items():
        console.print(f"  {key}. {name}")

    choice = Prompt.ask(
        "\nSelect provider",
        choices=list(providers.keys()),
        default="1",
    )

    provider, provider_name = providers[choice]
    console.print(f"\n[green]Selected: {provider_name}[/green]")

    # Get API key
    key_prompts = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "openai": "CUSTOM_OPENAI_API_KEY",
        "nanogpt": "NANOGPT_API_KEY",
    }

    key_env = key_prompts[provider]
    existing_key = os.getenv(key_env)

    if existing_key:
        use_existing = Confirm.ask(
            f"\n{key_env} already set in environment. Use it?",
            default=True,
        )
        if use_existing:
            api_key = f"${{{key_env}}}"
        else:
            api_key = Prompt.ask(f"\nEnter your {provider_name} API key")
    else:
        api_key = Prompt.ask(f"\nEnter your {provider_name} API key")

    # Get model
    default_models = {
        "anthropic": "claude-sonnet-4-5",
        "openrouter": "anthropic/claude-sonnet-4",
        "openai": "gpt-4o",
        "nanogpt": "moonshotai/Kimi-K2-Instruct-0905",
    }

    model = Prompt.ask(
        "\nModel to use",
        default=default_models[provider],
    )

    config = {
        "provider": provider,
        "api_key": api_key,
        "model": model,
    }

    # Anthropic-specific: base URL
    if provider == "anthropic":
        custom_url = Confirm.ask(
            "\nUsing a custom base URL (e.g., clewdr)?",
            default=False,
        )
        if custom_url:
            config["base_url"] = Prompt.ask("Enter base URL")

    return config


def _setup_memory() -> dict:
    """Configure memory system."""
    console.print("\n[bold]Step 2: Memory System[/bold]\n")

    console.print("Clara uses mem0 for persistent memory. This requires:")
    console.print("  1. OpenAI API key (for embeddings)")
    console.print("  2. Vector store (PostgreSQL/pgvector or Qdrant)")

    # OpenAI key for embeddings
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        console.print("\n[green]OPENAI_API_KEY already set[/green]")
        embeddings_key = "${OPENAI_API_KEY}"
    else:
        embeddings_key = Prompt.ask("\nEnter your OpenAI API key (for embeddings)")

    # Vector store
    console.print("\nChoose your vector store:")
    console.print("  1. PostgreSQL with pgvector (production)")
    console.print("  2. Qdrant (development/local)")
    console.print("  3. Use defaults (will configure later)")

    store_choice = Prompt.ask(
        "\nSelect vector store",
        choices=["1", "2", "3"],
        default="3",
    )

    config = {
        "enabled": True,
        "openai_api_key": embeddings_key,
    }

    if store_choice == "1":
        db_url = os.getenv("MEM0_DATABASE_URL")
        if db_url:
            use_existing = Confirm.ask(
                "\nMEM0_DATABASE_URL already set. Use it?",
                default=True,
            )
            if not use_existing:
                db_url = Prompt.ask("\nEnter PostgreSQL connection URL")
        else:
            db_url = Prompt.ask(
                "\nEnter PostgreSQL connection URL",
                default="postgresql://user:pass@localhost:5432/clara_vectors",
            )
        config["database_url"] = db_url
        config["provider"] = "postgres"

    elif store_choice == "2":
        qdrant_url = os.getenv("QDRANT_URL")
        if qdrant_url:
            use_existing = Confirm.ask(
                f"\nQDRANT_URL already set ({qdrant_url}). Use it?",
                default=True,
            )
            if not use_existing:
                qdrant_url = Prompt.ask("\nEnter Qdrant URL")
        else:
            qdrant_url = Prompt.ask(
                "\nEnter Qdrant URL",
                default="http://localhost:6333",
            )
        config["qdrant_url"] = qdrant_url
        config["provider"] = "qdrant"

    else:
        config["provider"] = "default"

    # Graph memory (optional)
    enable_graph = Confirm.ask(
        "\nEnable graph memory (for relationship tracking)?",
        default=False,
    )
    if enable_graph:
        config["graph_enabled"] = True
        graph_provider = Prompt.ask(
            "Graph provider",
            choices=["neo4j", "kuzu"],
            default="kuzu",
        )
        config["graph_provider"] = graph_provider

    return config


def _setup_channels() -> dict:
    """Configure channels."""
    console.print("\n[bold]Step 3: Channels[/bold]\n")

    channels = {}

    # Discord
    setup_discord = Confirm.ask("Set up Discord integration?", default=True)
    if setup_discord:
        discord_token = os.getenv("DISCORD_BOT_TOKEN")
        if discord_token:
            use_existing = Confirm.ask(
                "\nDISCORD_BOT_TOKEN already set. Use it?",
                default=True,
            )
            if use_existing:
                token = "${DISCORD_BOT_TOKEN}"
            else:
                token = Prompt.ask("\nEnter Discord bot token")
        else:
            console.print("\nTo get a Discord bot token:")
            console.print("  1. Go to https://discord.com/developers/applications")
            console.print("  2. Create a new application")
            console.print("  3. Go to Bot tab and create a bot")
            console.print("  4. Copy the token")
            token = Prompt.ask("\nEnter Discord bot token")

        channels["discord"] = {
            "enabled": True,
            "token": token,
        }

        # Server/channel restrictions
        restrict = Confirm.ask(
            "\nRestrict to specific servers/channels?",
            default=False,
        )
        if restrict:
            servers = Prompt.ask(
                "Allowed server IDs (comma-separated, or leave blank for all)",
                default="",
            )
            if servers:
                channels["discord"]["allowed_servers"] = [
                    s.strip() for s in servers.split(",")
                ]

    # Telegram (optional)
    setup_telegram = Confirm.ask("\nSet up Telegram integration?", default=False)
    if setup_telegram:
        telegram_token = Prompt.ask("Enter Telegram bot token")
        channels["telegram"] = {
            "enabled": True,
            "token": telegram_token,
        }

    return channels


def _setup_gateway() -> dict:
    """Configure gateway settings."""
    console.print("\n[bold]Step 4: Gateway Settings[/bold]\n")

    config = {
        "host": "127.0.0.1",
        "port": 18789,
    }

    customize = Confirm.ask("Customize gateway settings?", default=False)

    if customize:
        config["host"] = Prompt.ask(
            "Bind address",
            default="127.0.0.1",
        )
        config["port"] = int(Prompt.ask(
            "Port",
            default="18789",
        ))

        use_secret = Confirm.ask("Set a shared secret for authentication?", default=False)
        if use_secret:
            config["secret"] = Prompt.ask("Enter shared secret")

    return config


def _save_config(config: dict) -> None:
    """Save configuration to file."""
    import yaml

    config_dir = Path.home() / ".clara"
    config_dir.mkdir(parents=True, exist_ok=True)

    config_path = config_dir / "config.yaml"

    # Build the config structure
    yaml_config = {
        "llm": {
            "provider": config["llm"]["provider"],
            "model": config["llm"]["model"],
        },
        "memory": {
            "enabled": config["memory"].get("enabled", True),
        },
        "gateway": config["gateway"],
    }

    # Add API key (might be env var reference)
    api_key = config["llm"].get("api_key", "")
    if api_key.startswith("${"):
        yaml_config["llm"]["api_key"] = api_key
    else:
        # Save to env file instead
        _save_env_var(f"{config['llm']['provider'].upper()}_API_KEY", api_key)

    # Add base URL if present
    if "base_url" in config["llm"]:
        yaml_config["llm"]["base_url"] = config["llm"]["base_url"]

    # Memory config
    if config["memory"].get("provider") == "postgres":
        db_url = config["memory"].get("database_url", "")
        if db_url.startswith("${"):
            yaml_config["memory"]["database_url"] = db_url
        else:
            _save_env_var("MEM0_DATABASE_URL", db_url)
    elif config["memory"].get("provider") == "qdrant":
        yaml_config["memory"]["qdrant_url"] = config["memory"].get("qdrant_url")

    if config["memory"].get("graph_enabled"):
        yaml_config["memory"]["graph_enabled"] = True
        yaml_config["memory"]["graph_provider"] = config["memory"].get("graph_provider")

    # OpenAI key for embeddings
    openai_key = config["memory"].get("openai_api_key", "")
    if openai_key and not openai_key.startswith("${"):
        _save_env_var("OPENAI_API_KEY", openai_key)

    # Channels
    if config.get("channels"):
        yaml_config["channels"] = {}
        for channel_name, channel_config in config["channels"].items():
            yaml_config["channels"][channel_name] = {
                "enabled": channel_config.get("enabled", True),
            }

            # Handle token
            token = channel_config.get("token", "")
            if token.startswith("${"):
                yaml_config["channels"][channel_name]["token"] = token
            else:
                env_name = f"{channel_name.upper()}_BOT_TOKEN"
                _save_env_var(env_name, token)
                yaml_config["channels"][channel_name]["token"] = f"${{{env_name}}}"

            # Add other settings
            if "allowed_servers" in channel_config:
                yaml_config["channels"][channel_name]["allowed_servers"] = channel_config["allowed_servers"]

    # Write config
    with open(config_path, "w") as f:
        yaml.dump(yaml_config, f, default_flow_style=False, sort_keys=False)

    console.print(f"\n[green]Configuration saved to {config_path}[/green]")


def _save_env_var(name: str, value: str) -> None:
    """Save an environment variable to .env file."""
    env_file = Path.home() / ".clara" / ".env"

    # Read existing content
    existing = {}
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    key, val = line.split("=", 1)
                    existing[key] = val

    # Update
    existing[name] = value

    # Write back
    with open(env_file, "w") as f:
        for key, val in existing.items():
            f.write(f"{key}={val}\n")

    # Set restrictive permissions
    env_file.chmod(0o600)

    console.print(f"[dim]Saved {name} to {env_file}[/dim]")
