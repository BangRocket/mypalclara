"""Discord adapter - thin bot that delegates to ClaraFlow.

This is a minimal Discord.py bot that:
- Listens for Discord events
- Packages them into structured context
- Delegates to ClaraFlow for processing
- Sends responses back to Discord
"""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

import discord
from discord import Message as DiscordMessage

from clara_core import init_platform
from clara_core.llm import make_llm
from clara_core.memory import MemoryManager
from db.channel_config import should_respond_to_message

from .helpers import (
    build_participants_list,
    chunk_response,
    clean_message_content,
    get_or_create_thread_id,
)

if TYPE_CHECKING:
    pass


class ClaraDiscordBot(discord.Client):
    """Thin Discord bot that delegates to ClaraFlow.

    Handles:
    - Discord event listening
    - Message filtering (mentions, channel modes)
    - Context packaging
    - Response sending

    Does NOT handle:
    - LLM calls (delegated to ClaraFlow)
    - Memory operations (delegated to ClaraFlow)
    - Tool execution (v2)
    """

    def __init__(self):
        """Initialize the Discord bot."""
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.guilds = True
        intents.members = True

        super().__init__(intents=intents)

        # Initialize platform (loads mem0, etc.)
        init_platform()

        # Initialize MemoryManager with LLM
        llm = make_llm()
        MemoryManager.initialize(llm)

        print("[adapter] ClaraDiscordBot initialized")

    async def on_ready(self):
        """Called when bot is connected and ready."""
        print(f"[adapter] Logged in as {self.user} (ID: {self.user.id})")
        print(f"[adapter] Connected to {len(self.guilds)} guilds")

    async def on_message(self, message: DiscordMessage):
        """Handle incoming messages.

        Args:
            message: The Discord message
        """
        # Ignore own messages
        if message.author == self.user:
            return

        # Ignore bot messages
        if message.author.bot:
            return

        # Check if DM
        is_dm = message.guild is None

        # For non-DMs, check if we should respond
        if not is_dm:
            is_mentioned = self.user.mentioned_in(message)
            is_reply_to_bot = (
                message.reference
                and message.reference.resolved
                and message.reference.resolved.author == self.user
            )

            # Check channel mode
            channel_id_str = str(message.channel.id)
            if not should_respond_to_message(channel_id_str, is_mentioned or is_reply_to_bot):
                return

        # Clean message content
        content = clean_message_content(message.content, self.user.id)
        if not content.strip():
            return

        # Build context
        from crews.clara_flow.state import ConversationContext

        context = ConversationContext(
            user_id=f"discord-{message.author.id}",
            platform="discord",
            channel_id=str(message.channel.id),
            guild_id=str(message.guild.id) if message.guild else None,
            is_dm=is_dm,
            user_display_name=message.author.display_name,
            guild_name=message.guild.name if message.guild else None,
            channel_name=getattr(message.channel, "name", "DM"),
            thread_id=get_or_create_thread_id(message),
            participants=build_participants_list(message),
        )

        # Show typing indicator while processing
        async with message.channel.typing():
            try:
                response = await self._run_flow(context, content)
            except Exception as e:
                print(f"[adapter] Error running flow: {e}")
                import traceback
                traceback.print_exc()
                response = "I ran into an issue processing that. Let me try again?"

        # Send response
        if response:
            await self._send_response(message, response)

    async def _run_flow(
        self,
        context: "ConversationContext",
        content: str,
    ) -> str:
        """Run ClaraFlow in executor (sync -> async bridge).

        Args:
            context: Conversation context
            content: Message content

        Returns:
            Clara's response
        """
        loop = asyncio.get_event_loop()

        def run_sync():
            from crews.clara_flow import ClaraFlow

            flow = ClaraFlow()
            flow.kickoff(
                inputs={
                    "context": context,
                    "user_message": content,
                    "recent_messages": [],
                    "tier": "mid",
                }
            )
            return flow.state.response

        return await loop.run_in_executor(None, run_sync)

    async def _send_response(
        self,
        message: DiscordMessage,
        response: str,
    ) -> None:
        """Send response back to Discord.

        Handles chunking for long responses.

        Args:
            message: Original message to reply to
            response: Response content
        """
        chunks = chunk_response(response)

        for i, chunk in enumerate(chunks):
            if i == 0:
                # First chunk - reply to original message
                await message.reply(chunk, mention_author=False)
            else:
                # Subsequent chunks - just send to channel
                await message.channel.send(chunk)


def run_bot():
    """Run the Discord bot."""
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise ValueError("DISCORD_BOT_TOKEN not set")

    bot = ClaraDiscordBot()
    bot.run(token)


if __name__ == "__main__":
    run_bot()
