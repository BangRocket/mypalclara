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
    HEALTH_PORT - Port for health check server (default: 18790)
    SHUTDOWN_GRACE_PERIOD - Seconds to wait for pending requests (default: 30)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
import threading
from datetime import datetime
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import uvicorn

from config.logging import get_logger, init_logging
from gateway.events import Event, EventType, emit, get_event_emitter, on
from gateway.health import health_app, set_gateway_components
from gateway.hooks import get_hook_manager
from gateway.processor import MessageProcessor
from gateway.providers import DiscordProvider, EmailProvider, get_provider_manager
from gateway.scheduler import get_scheduler
from gateway.server import GatewayServer

init_logging()
logger = get_logger("gateway")


async def email_alert_consumer(event: Event) -> None:
    """Handle email alerts by sending Discord notifications.

    Only processes events from the email platform. Formats the email
    info into a Discord message and sends via DiscordProvider.
    """
    # Only handle email platform events
    if event.platform != "email":
        return

    # Get provider manager to access Discord provider
    manager = get_provider_manager()
    discord_provider = manager.get("discord")

    if not discord_provider or not discord_provider.running:
        logger.warning("Discord provider not available for email alert")
        return

    # Extract email data
    data = event.data
    from_addr = data.get("from", "Unknown")
    subject = data.get("subject", "No Subject")
    preview = data.get("preview", "")[:200]  # Truncate preview

    # Format the alert message
    message = (
        f"**New Email Alert**\n"
        f"From: {from_addr}\n"
        f"Subject: {subject}\n"
        f"Preview: {preview}..."
    )

    # Get target user from event
    # user_id format is "discord-{discord_user_id}" (set by EmailProvider)
    user_id = event.user_id

    if not user_id:
        logger.warning("Email alert has no target user_id")
        return

    # Extract Discord user ID from prefixed user_id (e.g., "discord-123456" -> "123456")
    # This matches the format set by email monitoring rules
    discord_user_id = user_id
    if user_id.startswith("discord-"):
        discord_user_id = user_id[8:]  # Remove "discord-" prefix

    # Get the Discord channel object for DM routing
    # DiscordProvider.send_response() requires context["channel"] to be an actual
    # Discord channel object with a .send() method, NOT a string channel_id
    bot = discord_provider.bot
    if bot is None:
        logger.warning("Discord bot not initialized")
        return

    try:
        # Fetch the Discord User object
        discord_user = await bot.fetch_user(int(discord_user_id))
        # Create/get the DM channel for this user
        dm_channel = await discord_user.create_dm()
    except Exception as e:
        logger.warning(f"Failed to get DM channel for user {discord_user_id}: {e}")
        return

    # Build context with the actual Discord channel object
    context = {
        "channel": dm_channel,  # REQUIRED: actual Discord channel object
        "user_id": user_id,
        "is_alert": True,  # Flag to indicate this is an automated alert
    }

    try:
        await discord_provider.send_response(context, message)
        logger.info(f"Sent email alert to {user_id}: {subject}")
    except Exception as e:
        logger.exception(f"Failed to send email alert: {e}")


def run_health_server(port: int) -> None:
    """Run health check server in background thread."""
    config = uvicorn.Config(
        health_app,
        host="0.0.0.0",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    server.run()


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

    # Register email alert consumer if both providers are enabled
    if enable_discord and enable_email:
        on(EventType.MESSAGE_RECEIVED, email_alert_consumer)
        logger.info("Email alert consumer registered")

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

    # Track startup time
    started_at = datetime.now()

    # Wire up health checks
    set_gateway_components(server, processor, started_at)

    # Start health check server
    health_port = int(os.getenv("HEALTH_PORT", "18790"))
    health_thread = threading.Thread(
        target=run_health_server,
        args=(health_port,),
        daemon=True
    )
    health_thread.start()
    logger.info(f"Health check server started on port {health_port}")

    # Emit startup event
    await emit(
        Event(
            type=EventType.GATEWAY_STARTUP,
            data={
                "host": host,
                "port": port,
                "health_port": health_port,
                "hooks_loaded": hooks_loaded,
                "tasks_loaded": tasks_loaded,
            },
        )
    )

    # Set up graceful shutdown
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()
    shutdown_started = False

    async def graceful_shutdown(sig_name: str) -> None:
        """Gracefully shutdown, completing pending tasks."""
        nonlocal shutdown_started
        if shutdown_started:
            return
        shutdown_started = True

        logger.info(f"Received {sig_name}, starting graceful shutdown...")

        # Emit shutdown event
        await emit(
            Event(
                type=EventType.GATEWAY_SHUTDOWN,
                data={"reason": sig_name},
            )
        )

        # Get pending tasks from router
        router_stats = await server.router.get_stats()
        pending_count = router_stats.get("active_channels", 0) + router_stats.get("total_queued", 0)

        if pending_count > 0:
            logger.info(f"Waiting for {pending_count} pending requests to complete...")

            # Give pending tasks time to complete (max 30 seconds)
            grace_period = int(os.getenv("SHUTDOWN_GRACE_PERIOD", "30"))
            deadline = asyncio.get_event_loop().time() + grace_period
            remaining = pending_count

            while asyncio.get_event_loop().time() < deadline:
                router_stats = await server.router.get_stats()
                remaining = router_stats.get("active_channels", 0) + router_stats.get("total_queued", 0)
                if remaining == 0:
                    logger.info("All pending requests completed")
                    break
                await asyncio.sleep(0.5)
            else:
                logger.warning(f"Grace period expired, {remaining} requests may be interrupted")

        # Stop accepting new connections
        logger.info("Stopping gateway services...")

        # Stop providers first (graceful shutdown)
        if provider_manager.providers:
            logger.info("Stopping providers...")
            await provider_manager.stop_all()
            logger.info("All providers stopped")

        await scheduler.stop()
        await server.stop()

        # Cancel remaining tasks
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if tasks:
            logger.info(f"Cancelling {len(tasks)} remaining tasks")
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        stop_event.set()

    def signal_handler(sig_name: str):
        asyncio.create_task(graceful_shutdown(sig_name))

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: signal_handler(s.name))

    logger.info("Gateway ready and accepting connections")
    logger.info(f"Connect adapters to: ws://{host}:{port}")
    logger.info(f"Health checks: http://0.0.0.0:{health_port}/health")

    # Wait for shutdown
    await stop_event.wait()
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
