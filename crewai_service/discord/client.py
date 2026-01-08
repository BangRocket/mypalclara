"""Discord client - thin bot that delegates to Crew and Flow.

This is a minimal Discord.py bot that:
- Listens for Discord events
- Delegates message processing to DiscordCrew
- Runs ClaraFlow for response generation
- Handles async/sync bridging for CrewAI
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
from clara_core.db import SessionLocal
from clara_core.db.channel_config import should_respond_to_message

from crewai_service.crews.discord.crew import DiscordCrew
from crewai_service.contracts.messages import InboundMessage, OutboundMessage

if TYPE_CHECKING:
    pass


class ClaraDiscordClient(discord.Client):
    """Thin Discord client that delegates to Crew and Flow.

    Handles:
    - Discord event listening
    - Message filtering (mentions, channel modes)
    - Async/sync bridging for CrewAI Flow

    Does NOT handle:
    - Message content processing (delegated to Crew)
    - Response generation (delegated to Flow)
    - Memory operations (delegated to Flow)
    """

    def __init__(self):
        """Initialize the Discord client."""
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

        # Crew will be initialized after we have our user
        self._crew: DiscordCrew | None = None

        print("[client] ClaraDiscordClient initialized")

    async def on_ready(self):
        """Called when bot is connected and ready."""
        print(f"[client] Logged in as {self.user} (ID: {self.user.id})")
        print(f"[client] Connected to {len(self.guilds)} guilds")

        # Initialize crew now that we have our user
        self._crew = DiscordCrew(self.user)

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

        # Check if we should respond
        if not self._should_respond(message):
            return

        # Ensure crew is initialized
        if not self._crew:
            print("[client] Crew not initialized yet, skipping message")
            return

        # Show typing indicator while processing
        async with message.channel.typing():
            try:
                # Crew receives and normalizes the message
                inbound = await self._crew.receive(message)

                # Skip empty messages
                if not inbound.content.strip():
                    return

                # Flow processes and generates response
                outbound = await self._run_flow(inbound)

                # Crew delivers the response
                await self._crew.deliver(outbound, message)

            except Exception as e:
                print(f"[client] Error processing message: {e}")
                import traceback
                traceback.print_exc()

                # Send error response
                error_response = OutboundMessage(
                    content="I ran into an issue processing that. Let me try again?"
                )
                await self._crew.deliver(error_response, message)

    def _should_respond(self, message: DiscordMessage) -> bool:
        """Check if the bot should respond to this message.

        Args:
            message: Discord message

        Returns:
            True if should respond
        """
        # Always respond to DMs
        if message.guild is None:
            return True

        # Check if mentioned or replying to bot
        is_mentioned = self.user.mentioned_in(message)
        is_reply_to_bot = (
            message.reference
            and message.reference.resolved
            and message.reference.resolved.author == self.user
        )

        # Check channel mode
        channel_id_str = str(message.channel.id)
        return should_respond_to_message(channel_id_str, is_mentioned or is_reply_to_bot)

    async def _run_flow(self, inbound: InboundMessage) -> OutboundMessage:
        """Run ClaraFlow in executor (sync -> async bridge).

        Args:
            inbound: Normalized inbound message from Crew

        Returns:
            OutboundMessage from the Flow
        """
        loop = asyncio.get_event_loop()

        def run_sync():
            from ..flow.clara import ClaraFlow

            # Get default tier from env, fallback to "mid"
            default_tier = os.getenv("MODEL_TIER", "mid")

            flow = ClaraFlow()
            result = flow.kickoff(inputs={
                "inbound": inbound,
                "tier": default_tier,
            })

            # Return the OutboundMessage from flow state
            return flow.state.outbound

        return await loop.run_in_executor(None, run_sync)


def run_bot():
    """Run the Discord bot."""
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise ValueError("DISCORD_BOT_TOKEN not set")

    bot = ClaraDiscordClient()
    bot.run(token)


if __name__ == "__main__":
    run_bot()
