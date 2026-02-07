"""Standalone Microsoft Teams adapter for the Clara Gateway.

This runs the Teams bot as a thin client that connects to the gateway
for all message processing.

Usage:
    poetry run python -m adapters.teams

Environment variables:
    TEAMS_APP_ID - Azure Bot registration App ID (required)
    TEAMS_APP_PASSWORD - Azure Bot registration password (required)
    TEAMS_APP_TYPE - App type: MultiTenant, SingleTenant, or ManagedIdentity (default: MultiTenant)
    TEAMS_APP_TENANT_ID - Tenant ID for SingleTenant apps (optional)
    TEAMS_PORT - Port to listen on (default: 3978)
    CLARA_GATEWAY_URL - Gateway WebSocket URL (default: ws://127.0.0.1:18789)
"""

from __future__ import annotations

import asyncio
import signal
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from aiohttp import web
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.integration.aiohttp import CloudAdapter, ConfigurationBotFrameworkAuthentication

from adapters.teams.bot import TeamsBot
from adapters.teams.gateway_client import TeamsGatewayClient
from clara_core.config import get_settings
from config.logging import get_logger, init_logging

init_logging()
logger = get_logger("adapters.teams")

# Configuration
_settings = get_settings()
GATEWAY_URL = _settings.gateway.url
PORT = _settings.teams.port


class BotConfig:
    """Bot Framework configuration for CloudAdapter.

    Note: Attribute names must match what ConfigurationBotFrameworkAuthentication expects:
    APP_ID, APP_PASSWORD, APP_TYPE, APP_TENANTID (not MicrosoftAppId, etc.)
    """

    PORT = PORT
    APP_ID = _settings.teams.app_id
    APP_PASSWORD = _settings.teams.app_password
    APP_TYPE = _settings.teams.app_type
    APP_TENANTID = _settings.teams.app_tenant_id


CONFIG = BotConfig()


async def messages(req: web.Request) -> web.Response:
    """Handle incoming Bot Framework activities."""
    # Handle CORS preflight
    if req.method == "OPTIONS":
        return web.Response(
            status=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
            },
        )

    bot: TeamsBot = req.app["bot"]
    adapter: CloudAdapter = req.app["adapter"]

    if "application/json" not in req.headers.get("Content-Type", ""):
        return web.Response(status=415)

    # Debug: log auth header (redacted)
    auth_header = req.headers.get("Authorization", "")
    if auth_header:
        # Just log the type and length, not the actual token
        parts = auth_header.split(" ", 1)
        if len(parts) == 2:
            logger.debug(f"Auth header: {parts[0]} (token length: {len(parts[1])})")
        else:
            logger.debug(f"Auth header format unexpected: {len(auth_header)} chars")
    else:
        logger.warning("No Authorization header in request")

    # CloudAdapter handles activity deserialization internally
    try:
        response = await adapter.process(req, bot)
        if response:
            return response
        return web.Response(status=200)
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        # Return 500 with error details for debugging
        return web.Response(status=500, text=str(e))


async def health(req: web.Request) -> web.Response:
    """Health check endpoint."""
    bot: TeamsBot = req.app["bot"]
    gateway_connected = bot.gateway_client.is_connected if bot.gateway_client else False
    return web.json_response(
        {
            "status": "healthy",
            "gateway_connected": gateway_connected,
        }
    )


async def on_startup(app: web.Application) -> None:
    """Initialize components on server startup."""
    logger.info("Starting Teams adapter...")

    # Debug: log credential status
    logger.info(f"APP_ID: {CONFIG.APP_ID}")
    logger.info(f"APP_PASSWORD: {'*' * len(CONFIG.APP_PASSWORD) if CONFIG.APP_PASSWORD else '(not set)'}")
    logger.info(f"APP_TYPE: {CONFIG.APP_TYPE}")
    if CONFIG.APP_TENANTID:
        logger.info(f"APP_TENANTID: {CONFIG.APP_TENANTID}")

    # Create CloudAdapter with ConfigurationBotFrameworkAuthentication
    # This is the modern, recommended approach that handles auth properly
    adapter = CloudAdapter(ConfigurationBotFrameworkAuthentication(CONFIG))

    # Add error handler to capture and log adapter-level errors
    async def on_error(context, error):
        logger.error(f"Adapter error: {error}", exc_info=True)
        # Try to send error message to user
        try:
            await context.send_activity("Sorry, something went wrong.")
        except Exception:
            pass

    adapter.on_turn_error = on_error

    # Create gateway client
    gateway_client = TeamsGatewayClient(gateway_url=GATEWAY_URL)

    # Create bot
    bot = TeamsBot(gateway_client=gateway_client)
    gateway_client.bot = bot

    # Store in app
    app["adapter"] = adapter
    app["bot"] = bot
    app["gateway_client"] = gateway_client

    # Start gateway client
    app["gateway_task"] = asyncio.create_task(gateway_client.start())

    logger.info(f"Teams adapter ready on port {PORT}")
    logger.info(f"Gateway: {GATEWAY_URL}")


async def on_shutdown(app: web.Application) -> None:
    """Cleanup on server shutdown."""
    logger.info("Shutting down Teams adapter...")

    # Stop gateway client
    gateway_client = app.get("gateway_client")
    if gateway_client:
        await gateway_client.disconnect()
        # Close Graph client
        if gateway_client._graph_client:
            await gateway_client._graph_client.close()

    gateway_task = app.get("gateway_task")
    if gateway_task:
        gateway_task.cancel()
        try:
            await gateway_task
        except asyncio.CancelledError:
            pass

    logger.info("Teams adapter stopped")


async def main() -> None:
    """Run the Teams adapter."""
    if not CONFIG.APP_ID:
        logger.error("TEAMS_APP_ID not set")
        sys.exit(1)

    if not CONFIG.APP_PASSWORD:
        logger.error("TEAMS_APP_PASSWORD not set")
        sys.exit(1)

    # Create aiohttp app with error middleware for better error visibility
    app = web.Application(middlewares=[aiohttp_error_middleware])
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    # Add routes
    app.router.add_post("/api/messages", messages)
    app.router.add_options("/api/messages", messages)  # CORS preflight
    app.router.add_get("/health", health)

    # Set up signal handlers
    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def signal_handler():
        logger.info("Received shutdown signal")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    # Run server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    logger.info(f"Bot listening on http://0.0.0.0:{PORT}")
    logger.info(f"Messaging endpoint: http://0.0.0.0:{PORT}/api/messages")

    # Wait for shutdown
    await stop_event.wait()

    # Cleanup
    await runner.cleanup()


def run() -> None:
    """Sync entry point for poetry scripts."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
