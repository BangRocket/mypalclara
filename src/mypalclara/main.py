"""
Main entry point for MyPalClara v0.8.0.

This module initializes the Cortex memory system and starts
the Discord bot.
"""

import asyncio
import logging
import sys

from mypalclara.adapters.discord import run_bot
from mypalclara import memory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point."""
    logger.info("Starting Clara v0.8.0...")

    # Initialize memory system
    await memory.initialize()
    logger.info("Memory system initialized")

    # Run Discord bot
    await run_bot()


if __name__ == "__main__":
    # Add src to path for imports
    src_path = str(__file__).rsplit("/mypalclara/", 1)[0]
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    asyncio.run(main())
