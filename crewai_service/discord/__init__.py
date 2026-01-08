"""Discord client for Clara.

Note: Imports are deferred to avoid circular import with crews.discord.
Use explicit imports:
    from crewai_service.discord.client import ClaraDiscordClient, run_bot
"""


def run_bot():
    """Run the Discord bot (lazy import to avoid circular import)."""
    from crewai_service.discord.client import run_bot as _run_bot
    _run_bot()


__all__ = ["run_bot"]
