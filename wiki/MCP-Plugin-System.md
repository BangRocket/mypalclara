# MCP Plugin System

Clara supports the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) for extensible tool capabilities, similar to Claude Code's `/plugins` command.

## Overview

MCP servers provide tools that Clara can use to interact with external services. Servers can be:
- **Local** - Run as subprocesses using stdio transport
- **Remote/Hosted** - Connect via HTTP transport (e.g., Smithery hosted)

## Installation Sources

### Smithery Registry (Local)

Install from the Smithery registry to run locally:

```
@Clara install the MCP server smithery:exa
```

The server runs as a local subprocess using the `@smithery/cli` runner.

### Smithery Hosted (OAuth)

Install hosted servers that run on Smithery's infrastructure:

```
@Clara install smithery-hosted:@smithery/notion
```

Hosted servers require OAuth authentication:
1. Install the server (status: `pending_auth`)
2. Start OAuth: `mcp_oauth_start(server_name="notion")`
3. Visit the authorization URL
4. Complete OAuth: `mcp_oauth_complete(server_name="notion", code="...")`

### npm Packages

Install any npm-published MCP server:

```
@Clara install @modelcontextprotocol/server-everything
```

### GitHub Repositories

Clone and build from GitHub:

```
@Clara install github.com/modelcontextprotocol/servers
```

### Docker Images

Run MCP servers in Docker containers:

```
@Clara install docker:ghcr.io/example/mcp-server:latest
```

### Local Paths

Use a local directory:

```
@Clara install /path/to/my-mcp-server
```

## Tool Naming

MCP tools use namespaced names to avoid conflicts:

```
{server_name}__{tool_name}
```

Examples:
- `everything__echo`
- `filesystem__read_file`
- `notion__search_pages`

## Management Commands

### Listing and Status

```
mcp_list                    # List all servers and tools
mcp_status(server="name")   # Detailed server status
```

### Server Control

```
mcp_enable(server="name")   # Enable a disabled server
mcp_disable(server="name")  # Disable without uninstalling
mcp_restart(server="name")  # Restart a running server
mcp_uninstall(server="name")  # Remove completely
```

### OAuth Management

```
mcp_oauth_start(server="name")  # Get authorization URL
mcp_oauth_complete(server="name", code="...")  # Exchange code
mcp_oauth_status(server="name")  # Check auth status
mcp_oauth_set_token(server="name", token="...")  # Manual token
```

## Multi-User Support

MCP servers support per-user isolation:

### User-Scoped Servers
- Each user can install their own servers
- Tools from user servers are only visible to that user
- OAuth tokens are stored per-user

### Global Servers
- Admins can install servers for all users (user_id=None)
- Global servers appear in everyone's tool list
- Useful for shared infrastructure tools

### Metrics Tracking
- Tool calls are tracked per-user
- Daily aggregated metrics for usage analysis
- Rate limiting per-user per-server

## Configuration Storage

### File-Based (Local Servers)

Local server configs are stored in `.mcp_servers/`:

```
.mcp_servers/
├── servers/
│   ├── everything.json
│   └── filesystem.json
├── remote/
│   └── notion.json
└── .oauth/
    └── notion.json
```

### Database (Multi-User)

The database stores:
- `mcp_servers` - Server registrations per user
- `mcp_oauth_tokens` - OAuth tokens per user
- `mcp_tool_calls` - Tool call history
- `mcp_usage_metrics` - Daily aggregated metrics
- `mcp_rate_limits` - Rate limiting configuration

## Permissions

Admin operations require one of:
- Discord Administrator permission
- Manage Channels permission
- Clara-Admin role

Admin operations:
- `mcp_install`
- `mcp_uninstall`
- `mcp_enable`
- `mcp_disable`
- `mcp_restart`

Non-admin users can:
- Use tools from their servers
- View server/tool lists
- Check OAuth status

## Best Practices

### Choosing Servers
- Prefer Smithery registry for curated servers
- Use hosted servers for services requiring auth
- Use local servers for filesystem or private data

### Resource Management
- Disable unused servers to save resources
- Monitor tool call metrics for usage patterns
- Set rate limits for expensive operations

### Security
- Review server permissions before installing
- Use per-user OAuth for hosted servers
- Don't expose sensitive data through MCP tools
