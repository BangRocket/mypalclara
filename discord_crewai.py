#!/usr/bin/env python3
"""Entry point for CrewAI-based Discord bot.

This replaces discord_bot.py with the new CrewAI architecture.
"""

import os
import sys

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def main():
    """Run the Discord bot."""
    # Check for required environment variables
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("ERROR: DISCORD_BOT_TOKEN not set")
        sys.exit(1)

    # Import and run
    from crews.discord.adapter import ClaraDiscordBot

    print("Starting Clara (CrewAI architecture)...")
    bot = ClaraDiscordBot()
    bot.run(token)


if __name__ == "__main__":
    main()
