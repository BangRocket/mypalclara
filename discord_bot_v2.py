#!/usr/bin/env python3
"""
Discord Bot v2 - LangGraph-based entry point.

This is the new entry point for MyPalClara v0.8.0 using the
LangGraph-based architecture. It runs separately from the
original discord_bot.py for comparison testing.

Usage:
    poetry run python discord_bot_v2.py

Environment:
    DISCORD_TOKEN - Discord bot token
    ANTHROPIC_API_KEY - Anthropic API key for Clara's reasoning
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("clara.v2")


async def main():
    """Main entry point for Clara v2."""
    logger.info("=" * 50)
    logger.info("MyPalClara v0.8.0 - LangGraph Architecture")
    logger.info("=" * 50)

    # Import after path setup
    from mypalclara.adapters.discord import run_bot
    from mypalclara import memory
    from mypalclara.metrics_server import (
        start_metrics_server,
        get_metrics_port,
        is_metrics_enabled,
    )

    # Initialize Cortex memory system
    logger.info("Initializing Cortex memory system...")
    await memory.initialize()
    logger.info("Cortex ready")

    # Start metrics server (for Prometheus scraping)
    if is_metrics_enabled():
        port = get_metrics_port()
        if start_metrics_server(port=port):
            logger.info(f"Prometheus metrics available at http://localhost:{port}/metrics")

    # Start Discord bot
    logger.info("Starting Discord bot...")
    await run_bot()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
