"""MCP (Model Context Protocol) client support for MindFlow agents.

This module provides native MCP client functionality, allowing MindFlow agents
to connect to any MCP-compliant server using various transport types.
"""

from mindflow.mcp.client import MCPClient
from mindflow.mcp.config import (
    MCPServerConfig,
    MCPServerHTTP,
    MCPServerSSE,
    MCPServerStdio,
)
from mindflow.mcp.filters import (
    StaticToolFilter,
    ToolFilter,
    ToolFilterContext,
    create_dynamic_tool_filter,
    create_static_tool_filter,
)
from mindflow.mcp.transports.base import BaseTransport, TransportType


__all__ = [
    "BaseTransport",
    "MCPClient",
    "MCPServerConfig",
    "MCPServerHTTP",
    "MCPServerSSE",
    "MCPServerStdio",
    "StaticToolFilter",
    "ToolFilter",
    "ToolFilterContext",
    "TransportType",
    "create_dynamic_tool_filter",
    "create_static_tool_filter",
]
