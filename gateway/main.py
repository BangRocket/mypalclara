"""Main entry point for the Clara Gateway.

Usage:
    poetry run python -m gateway
    poetry run python -m gateway --host 0.0.0.0 --port 18789

Environment variables:
    CLARA_GATEWAY_HOST - Bind address (default: 127.0.0.1)
    CLARA_GATEWAY_PORT - Port to listen on (default: 18789)
    CLARA_GATEWAY_SECRET - Shared secret for authentication (optional)
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
from gateway.processor import MessageProcessor
from gateway.server import GatewayServer

init_logging()
logger = get_logger("gateway")


async def main(host: str, port: int) -> None:
    """Run the gateway server.

    Args:
        host: Bind address
        port: Port to listen on
    """
    # Create server and processor
    server = GatewayServer(host=host, port=port)
    processor = MessageProcessor()

    # Wire them together
    server.set_processor(processor)

    # Initialize processor
    await processor.initialize()

    # Start server
    await server.start()

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

    # Cleanup
    logger.info("Shutting down gateway...")
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

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    try:
        asyncio.run(main(args.host, args.port))
    except KeyboardInterrupt:
        pass
