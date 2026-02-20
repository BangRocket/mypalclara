"""Entry point for running Discord adapter as a module.

Usage:
    python -m adapters.discord
"""

from mypalclara.adapters.discord.main import main

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
