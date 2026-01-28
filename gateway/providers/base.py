"""Provider abstract base class for gateway-embedded platform providers.

This module defines the Provider ABC that all platform providers (Discord, Email, CLI)
must implement to integrate with the Clara Gateway.

Unlike WebSocket-connected adapters, providers run inside the gateway process itself,
reducing latency and simplifying deployment for tightly-coupled platforms.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class PlatformMessage:
    """Normalized message format from any provider.

    Providers convert their platform-specific messages into this common format
    for processing by the gateway.
    """

    # Unified user ID (platform-prefixed, e.g., "discord-123", "email-user@example.com")
    user_id: str

    # Provider/platform identifier
    platform: str  # "discord", "email", "cli"

    # Original platform-specific user ID
    platform_user_id: str

    # Message content
    content: str

    # Channel/thread context
    channel_id: str | None = None
    thread_id: str | None = None

    # User display info
    user_name: str | None = None
    user_display_name: str | None = None

    # Attachments (normalized format)
    attachments: list[dict[str, Any]] = field(default_factory=list)

    # Timestamp
    timestamp: datetime = field(default_factory=datetime.now)

    # Platform-specific metadata for preserving original context
    metadata: dict[str, Any] = field(default_factory=dict)


class Provider(ABC):
    """Abstract base class for gateway-embedded platform providers.

    Providers handle the lifecycle and message handling for a specific platform.
    They run within the gateway process (not as external WebSocket clients).

    Lifecycle:
        1. Gateway calls start() during startup
        2. Provider normalizes incoming messages via normalize_message()
        3. Gateway processes messages and calls send_response() with results
        4. Gateway calls stop() during shutdown

    Example implementation:
        class DiscordProvider(Provider):
            @property
            def name(self) -> str:
                return "discord"

            async def start(self) -> None:
                await self.bot.start(self.token)

            async def stop(self) -> None:
                await self.bot.close()

            def normalize_message(self, msg: discord.Message) -> PlatformMessage:
                return PlatformMessage(...)

            async def send_response(self, context, content, files=None) -> None:
                await context["channel"].send(content)
    """

    def __init__(self) -> None:
        """Initialize the provider. Subclasses should call super().__init__()."""
        self._running = False

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider identifier (e.g., 'discord', 'email', 'cli').

        This name is used for:
        - Logging and monitoring
        - User ID prefixing (e.g., "discord-123")
        - Provider registry lookup

        Returns:
            Lowercase provider name string
        """
        ...

    @property
    def running(self) -> bool:
        """Check if the provider is currently running.

        Returns:
            True if start() has been called and stop() has not
        """
        return self._running

    @abstractmethod
    async def start(self) -> None:
        """Start the provider.

        This method should:
        - Initialize connections (bot login, IMAP connect, etc.)
        - Set up event handlers
        - Begin listening for messages

        The method should return once initialization is complete.
        Background tasks (like bot.run) should be spawned as tasks.

        Raises:
            Exception: If the provider fails to start
        """
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the provider gracefully.

        This method should:
        - Disconnect from the platform
        - Cancel any background tasks
        - Clean up resources

        Should not raise exceptions on double-stop.
        """
        ...

    @abstractmethod
    def normalize_message(self, platform_message: Any) -> PlatformMessage:
        """Convert a platform-specific message to normalized format.

        Args:
            platform_message: The platform-specific message object
                (e.g., discord.Message, email.message.Message)

        Returns:
            PlatformMessage with all fields populated

        Example:
            def normalize_message(self, msg: discord.Message) -> PlatformMessage:
                return PlatformMessage(
                    user_id=f"discord-{msg.author.id}",
                    platform="discord",
                    platform_user_id=str(msg.author.id),
                    content=msg.content,
                    channel_id=str(msg.channel.id),
                    user_name=msg.author.name,
                    user_display_name=msg.author.display_name,
                    metadata={"guild_id": str(msg.guild.id) if msg.guild else None}
                )
        """
        ...

    @abstractmethod
    async def send_response(
        self,
        context: dict[str, Any],
        content: str,
        files: list[str] | None = None,
    ) -> None:
        """Send a response back through the platform.

        Args:
            context: Platform-specific context dict containing whatever
                information is needed to send a reply. Typically includes:
                - channel: The channel/conversation to reply in
                - user: The user being replied to
                - message_id: Original message ID for threading
            content: The text content to send
            files: Optional list of file paths to attach

        Raises:
            Exception: If sending fails (provider should handle retries internally)
        """
        ...

    def format_user_id(self, platform_user_id: str) -> str:
        """Format a platform-specific user ID to unified format.

        Default implementation: {name}-{platform_user_id}

        Override this method if you need custom formatting.

        Args:
            platform_user_id: The original platform user ID

        Returns:
            Unified user ID string
        """
        return f"{self.name}-{platform_user_id}"

    def __repr__(self) -> str:
        """Return string representation of the provider."""
        status = "running" if self._running else "stopped"
        return f"<{self.__class__.__name__}(name={self.name!r}, status={status})>"
