"""Shared protocol types for adapters.

Re-exports gateway protocol types for adapter use.
"""

from mypalclara.gateway.protocol import (
    AttachmentInfo,
    ChannelInfo,
    GatewayMessage,
    MessageRequest,
    MessageType,
    ResponseChunk,
    ResponseEnd,
    ResponseStart,
    ToolResult,
    ToolStart,
    UserInfo,
)

__all__ = [
    "AttachmentInfo",
    "ChannelInfo",
    "GatewayMessage",
    "MessageRequest",
    "MessageType",
    "ResponseChunk",
    "ResponseEnd",
    "ResponseStart",
    "ToolResult",
    "ToolStart",
    "UserInfo",
]
