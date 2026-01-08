#!/usr/bin/env python3
"""Entry point for MindFlow-based Discord bot.

This replaces discord_bot.py with the new MindFlow architecture.

Architecture:
  Discord Bot (thin client)
         ↓
  Discord Crew (translates Discord ↔ Flow contract)
         ↓
  Clara Flow (mind - thinks, remembers, responds)
         ↓
  Discord Crew (formats response for Discord)
         ↓
  Discord Bot (delivers)
"""

import os
import sys
import warnings

# Suppress aiohttp deprecation warning from py-cord (fixed in future py-cord release)
# The warning comes from aiohttp's ws_connect when py-cord passes old-style timeout
import aiohttp.client

_original_ws_connect = aiohttp.client.ClientSession.ws_connect


async def _patched_ws_connect(self, url, **kwargs):
    # Convert old-style float timeout to new ClientWSTimeout if needed
    if "timeout" in kwargs and isinstance(kwargs["timeout"], (int, float)):
        from aiohttp import ClientWSTimeout

        kwargs["timeout"] = ClientWSTimeout(ws_close=kwargs["timeout"])
    return await _original_ws_connect(self, url, **kwargs)


aiohttp.client.ClientSession.ws_connect = _patched_ws_connect

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
    from clara_service.discord import run_bot

    print("Starting Clara (MindFlow architecture)...")
    run_bot()


if __name__ == "__main__":
    main()
