"""Main entry point for the Clara Gateway.

Usage:
    poetry run python -m gateway
    poetry run python -m gateway --host 0.0.0.0 --port 18789
    poetry run python -m gateway --enable-discord

Environment variables:
    CLARA_GATEWAY_HOST - Bind address (default: 127.0.0.1)
    CLARA_GATEWAY_PORT - Port to listen on (default: 18789)
    CLARA_GATEWAY_SECRET - Shared secret for authentication (optional)
    CLARA_HOOKS_DIR - Directory containing hooks.yaml (default: ./hooks)
    CLARA_SCHEDULER_DIR - Directory containing scheduler.yaml (default: .)
    CLARA_GATEWAY_DISCORD - Enable Discord provider (default: false)
    CLARA_GATEWAY_EMAIL - Enable Email provider (default: false)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from config.logging import get_logger, init_logging
from gateway.events import Event, EventType, emit, get_event_emitter
from gateway.hooks import get_hook_manager
from gateway.processor import MessageProcessor
from gateway.providers import DiscordProvider, EmailProvider, get_provider_manager
from gateway.scheduler import get_scheduler
from gateway.server import GatewayServer

init_logging()
logger = get_logger("gateway")


async def main(
    host: str, port: int, hooks_dir: str, scheduler_dir: str,
    enable_discord: bool, enable_email: bool
) -> None:
    """Run the gateway server.

    Args:
        host: Bind address
        port: Port to listen on
        hooks_dir: Directory containing hooks.yaml
        scheduler_dir: Directory containing scheduler.yaml
        enable_discord: Whether to start the Discord provider
        enable_email: Whether to start the Email provider
    """
    # Initialize hooks system
    hook_manager = get_hook_manager()
    hook_manager._hooks_dir = Path(hooks_dir)
    hooks_loaded = hook_manager.load_from_file()
    logger.info(f"Hooks system ready ({hooks_loaded} hooks loaded)")

    # Initialize scheduler
    scheduler = get_scheduler()
    scheduler._config_dir = Path(scheduler_dir)
    tasks_loaded = scheduler.load_from_file()
    logger.info(f"Scheduler ready ({tasks_loaded} tasks loaded)")

    # Initialize provider manager
    provider_manager = get_provider_manager()

    # Register Discord provider if enabled
    if enable_discord:
        discord_provider = DiscordProvider()
        provider_manager.register(discord_provider)
        logger.info("Discord provider registered")

    # Register Email provider if enabled
    if enable_email:
        email_provider = EmailProvider()
        provider_manager.register(email_provider)
        logger.info("Email provider registered")

    # Create server and processor
    server = GatewayServer(host=host, port=port)
    processor = MessageProcessor()

    # Wire them together
    server.set_processor(processor)

    # Initialize processor
    await processor.initialize()

    # Start scheduler
    await scheduler.start()

    # Start server
    await server.start()

    # Start registered providers
    if provider_manager.providers:
        logger.info(f"Starting {len(provider_manager.providers)} provider(s)...")
        await provider_manager.start_all()
        logger.info("All providers started")

    # Emit startup event
    await emit(
        Event(
            type=EventType.GATEWAY_STARTUP,
            data={
                "host": host,
                "port": port,
                "hooks_loaded": hooks_loaded,
                "tasks_loaded": tasks_loaded,
            },
        )
    )

    # Set up signal handlers
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def signal_handler():
        logger.info("Received shutdown signal")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    logger.info("Gateway ready and accepting connections")
    logger.info(f"Connect adapters to: ws://{host}:{port}")

    # Wait for shutdown
    await stop_event.wait()

    # Emit shutdown event (before stopping services)
    await emit(
        Event(
            type=EventType.GATEWAY_SHUTDOWN,
            data={"reason": "signal"},
        )
    )

    # Cleanup
    logger.info("Shutting down gateway...")

    # Stop providers first (graceful shutdown)
    if provider_manager.providers:
        logger.info("Stopping providers...")
        await provider_manager.stop_all()
        logger.info("All providers stopped")

    await scheduler.stop()
    await server.stop()
    logger.info("Gateway stopped")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Clara Gateway Server")

    parser.add_argument(
        "--host",
        default=os.getenv("CLARA_GATEWAY_HOST", "127.0.0.1"),
        help="Bind address (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("CLARA_GATEWAY_PORT", "18789")),
        help="Port to listen on (default: 18789)",
    )
    parser.add_argument(
        "--hooks-dir",
        default=os.getenv("CLARA_HOOKS_DIR", "./hooks"),
        help="Directory containing hooks.yaml (default: ./hooks)",
    )
    parser.add_argument(
        "--scheduler-dir",
        default=os.getenv("CLARA_SCHEDULER_DIR", "."),
        help="Directory containing scheduler.yaml (default: .)",
    )
    parser.add_argument(
        "--enable-discord",
        action="store_true",
        default=os.getenv("CLARA_GATEWAY_DISCORD", "false").lower() == "true",
        help="Enable Discord provider (default: $CLARA_GATEWAY_DISCORD or false)",
    )
    parser.add_argument(
        "--enable-email",
        action="store_true",
        default=os.getenv("CLARA_GATEWAY_EMAIL", "false").lower() == "true",
        help="Enable Email provider (default: $CLARA_GATEWAY_EMAIL or false)",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    try:
        asyncio.run(
            main(
                args.host,
                args.port,
                args.hooks_dir,
                args.scheduler_dir,
                args.enable_discord,
                args.enable_email,
            )
        )
    except KeyboardInterrupt:
        pass
