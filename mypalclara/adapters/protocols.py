"""Capability protocols for platform adapters.

These protocols define the interface contracts for adapter capabilities.
Adapters implement the protocols that correspond to their declared capabilities.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from mypalclara.gateway.protocol import ButtonInfo, FileData, GatewayMessage


@runtime_checkable
class MessagingAdapter(Protocol):
    """Core messaging capability (required for all adapters).

    Every adapter must implement these methods to handle the basic
    request/response flow with the gateway.
    """

    async def on_response_start(self, message: GatewayMessage) -> None:
        """Handle response generation started.

        Called when the gateway begins generating a response.
        Typically used to show typing indicators or "thinking" status.

        Args:
            message: ResponseStart message from gateway
        """
        ...

    async def on_response_chunk(self, message: GatewayMessage) -> None:
        """Handle streaming response chunk.

        Called for each chunk of streamed text during response generation.
        May be called many times during a single response.

        Args:
            message: ResponseChunk message from gateway
        """
        ...

    async def on_response_end(self, message: GatewayMessage) -> None:
        """Handle response generation complete.

        Called when the full response is ready. Contains the complete
        response text and any files to attach.

        Args:
            message: ResponseEnd message from gateway
        """
        ...


@runtime_checkable
class ToolAdapter(Protocol):
    """Tool execution display capability.

    Adapters implementing this can show tool execution status to users.
    """

    async def on_tool_start(self, message: GatewayMessage) -> None:
        """Handle tool execution started.

        Called when a tool begins executing. Used to show status
        like "Running Python code..." to the user.

        Args:
            message: ToolStart message from gateway
        """
        ...

    async def on_tool_result(self, message: GatewayMessage) -> None:
        """Handle tool execution completed.

        Called when a tool finishes executing with success/failure status.

        Args:
            message: ToolResult message from gateway
        """
        ...


@runtime_checkable
class StreamingAdapter(Protocol):
    """Real-time streaming display capability.

    Adapters implementing this can update messages in real-time
    as response chunks arrive (e.g., editing a message repeatedly).
    """

    async def show_typing(self) -> None:
        """Show typing indicator to the user.

        Called to indicate the assistant is "thinking" or generating.
        Platform-specific implementation (e.g., Discord typing indicator,
        Slack "..." status, or CLI spinner).
        """
        ...

    async def update_streaming_message(
        self,
        request_id: str,
        accumulated_text: str,
    ) -> None:
        """Update the streaming message with accumulated text.

        Called to update the visible message as new chunks arrive.
        For platforms that support message editing.

        Args:
            request_id: The request ID for tracking
            accumulated_text: Full accumulated response text so far
        """
        ...


@runtime_checkable
class AttachmentAdapter(Protocol):
    """File/image handling capability.

    Adapters implementing this can extract attachments from incoming
    messages and send files with outgoing responses.
    """

    async def extract_attachments(self, message: Any) -> list[dict[str, Any]]:
        """Extract attachments from a platform message.

        Args:
            message: Platform-specific message object

        Returns:
            List of attachment info dicts with type, filename, base64_data, etc.
        """
        ...

    async def send_files(
        self,
        channel: Any,
        files: list[FileData],
    ) -> None:
        """Send files to a channel.

        Args:
            channel: Platform-specific channel object
            files: List of FileData with filename, content_base64, media_type
        """
        ...


@runtime_checkable
class ReactionAdapter(Protocol):
    """Emoji reaction capability.

    Adapters implementing this can add emoji reactions to messages.
    """

    async def add_reaction(
        self,
        message: Any,
        emoji: str,
    ) -> None:
        """Add an emoji reaction to a message.

        Args:
            message: Platform-specific message object
            emoji: Emoji string (e.g., "👍", ":thumbsup:", etc.)
        """
        ...


@runtime_checkable
class EditableAdapter(Protocol):
    """Message editing capability.

    Adapters implementing this can edit previously sent messages.
    """

    async def edit_message(
        self,
        message: Any,
        new_content: str,
        **kwargs: Any,
    ) -> None:
        """Edit a previously sent message.

        Args:
            message: Platform-specific message object to edit
            new_content: New message content
            **kwargs: Additional platform-specific options (embeds, components, etc.)
        """
        ...


@runtime_checkable
class ThreadAdapter(Protocol):
    """Thread/reply chain support capability.

    Adapters implementing this can create and manage message threads.
    """

    async def create_thread(
        self,
        message: Any,
        name: str,
        **kwargs: Any,
    ) -> Any:
        """Create a thread from a message.

        Args:
            message: Platform-specific message to create thread from
            name: Thread name/title
            **kwargs: Additional options (auto_archive_duration, etc.)

        Returns:
            Platform-specific thread object
        """
        ...

    async def reply_in_thread(
        self,
        thread: Any,
        content: str,
        **kwargs: Any,
    ) -> Any:
        """Send a reply in a thread.

        Args:
            thread: Platform-specific thread object
            content: Message content
            **kwargs: Additional options

        Returns:
            Platform-specific message object
        """
        ...


@runtime_checkable
class ButtonAdapter(Protocol):
    """Interactive button/component capability.

    Adapters implementing this can add interactive buttons to messages.
    """

    async def create_button_view(
        self,
        buttons: list[ButtonInfo],
    ) -> Any:
        """Create a button view/component from button info.

        Args:
            buttons: List of ButtonInfo with label, style, action

        Returns:
            Platform-specific view/component object
        """
        ...


@runtime_checkable
class EmbedAdapter(Protocol):
    """Rich embed/card capability.

    Adapters implementing this can send rich formatted cards/embeds.
    """

    async def create_embed(
        self,
        title: str,
        description: str | None = None,
        color: int | str | None = None,
        fields: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Create a rich embed/card.

        Args:
            title: Embed title
            description: Embed description
            color: Color (hex int or string)
            fields: List of field dicts with name, value, inline
            **kwargs: Additional options (footer, thumbnail, image, etc.)

        Returns:
            Platform-specific embed/card object
        """
        ...


@runtime_checkable
class MentionAdapter(Protocol):
    """User/channel mention capability.

    Adapters implementing this can format and handle @mentions.
    """

    def format_user_mention(self, user_id: str) -> str:
        """Format a user mention for this platform.

        Args:
            user_id: Platform-specific user ID

        Returns:
            Formatted mention string (e.g., "<@123456>", "@username")
        """
        ...

    def format_channel_mention(self, channel_id: str) -> str:
        """Format a channel mention for this platform.

        Args:
            channel_id: Platform-specific channel ID

        Returns:
            Formatted mention string (e.g., "<#123456>", "#channel")
        """
        ...


# Capability name to protocol mapping
CAPABILITY_PROTOCOLS: dict[str, type] = {
    "messaging": MessagingAdapter,
    "tools": ToolAdapter,
    "streaming": StreamingAdapter,
    "attachments": AttachmentAdapter,
    "reactions": ReactionAdapter,
    "editing": EditableAdapter,
    "threads": ThreadAdapter,
    "buttons": ButtonAdapter,
    "embeds": EmbedAdapter,
    "mentions": MentionAdapter,
}


def get_protocol_for_capability(capability: str) -> type | None:
    """Get the protocol class for a capability name.

    Args:
        capability: Capability name (e.g., "streaming", "attachments")

    Returns:
        Protocol class or None if not found
    """
    return CAPABILITY_PROTOCOLS.get(capability)


def check_protocol_compliance(
    adapter: Any,
    capability: str,
) -> bool:
    """Check if an adapter implements a capability's protocol.

    Args:
        adapter: Adapter instance to check
        capability: Capability name to verify

    Returns:
        True if adapter implements the protocol
    """
    protocol = get_protocol_for_capability(capability)
    if protocol is None:
        return True  # Unknown capability, assume compliant

    return isinstance(adapter, protocol)


def get_missing_capabilities(
    adapter: Any,
    declared_capabilities: list[str],
) -> list[str]:
    """Get list of capabilities the adapter claims but doesn't implement.

    Args:
        adapter: Adapter instance to check
        declared_capabilities: Capabilities declared in manifest

    Returns:
        List of capability names that are declared but not implemented
    """
    missing = []
    for capability in declared_capabilities:
        if not check_protocol_compliance(adapter, capability):
            missing.append(capability)
    return missing
