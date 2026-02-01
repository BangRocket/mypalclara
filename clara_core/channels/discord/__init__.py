"""Discord channel plugin for Clara.

Implements the ChannelPlugin interface for Discord integration.
This is a core channel that provides full Discord support including:
- Streaming responses
- Threading/replies
- Rich embeds
- Slash commands
- Reactions
- Attachments and images
"""

from clara_core.channels.discord.plugin import DiscordPlugin, create_discord_plugin

__all__ = ["DiscordPlugin", "create_discord_plugin"]
