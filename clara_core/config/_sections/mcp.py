"""MCP plugin configuration models."""

from pydantic import BaseModel


class MCPSettings(BaseModel):
    servers_dir: str = ".mcp_servers"
    oauth_dir: str = ""
    smithery_api_key: str = ""
