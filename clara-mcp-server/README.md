# Clara MCP Server

A native MCP (Model Context Protocol) server written in Rust that exposes Clara's core tools. This server runs as a stdio-based MCP server and integrates with Clara's Discord bot or any MCP-compatible client.

## Features

- **Database Backups** - Automated backup management for Clara and Mem0 databases to S3, Google Drive, or FTP
- **Claude Code Integration** - Execute coding tasks via Claude Code CLI
- **Sandbox Execution** - Run Python code and shell commands in isolated environments
- **ORS Notes** - Organic Response System note management

## Building

```bash
cd clara-mcp-server
cargo build --release
```

The binary will be at `target/release/clara-mcp-server`.

## Running

```bash
# Direct execution (stdio mode)
./target/release/clara-mcp-server

# With debug logging
RUST_LOG=debug ./target/release/clara-mcp-server
```

## Configuration

The server reads configuration from environment variables:

| Variable | Description |
|----------|-------------|
| `CLARA_API_URL` | API service URL for backup operations (default: http://localhost:8000) |
| `DATABASE_URL` | PostgreSQL connection string for ORS notes |
| `SANDBOX_API_URL` | Remote sandbox service URL |
| `SANDBOX_API_KEY` | Remote sandbox API key |

## Available Tools

### Backup (7 tools)
| Tool | Description |
|------|-------------|
| `backup_now` | Trigger an immediate database backup |
| `backup_list` | List available database backups with optional filters |
| `backup_status` | Get current backup status including last backup time and schedule |
| `backup_schedule` | Configure the backup schedule using cron expressions |
| `backup_config` | Add or update a backup destination (S3, Google Drive, FTP/SFTP) |
| `backup_destinations` | List all configured backup destinations |
| `backup_destination_delete` | Remove a backup destination by name |

### Claude Code (4 tools)
| Tool | Description |
|------|-------------|
| `claude_code` | Execute a coding task using Claude Code CLI |
| `claude_code_status` | Check Claude Code availability and status |
| `claude_code_get_workdir` | Get the current working directory |
| `claude_code_set_workdir` | Set the working directory |

### Sandbox (6 tools)
| Tool | Description |
|------|-------------|
| `execute_python` | Execute Python code in a sandboxed environment |
| `install_package` | Install a Python package in the sandbox |
| `sandbox_read_file` | Read a file from the sandbox |
| `sandbox_write_file` | Write content to a file in the sandbox |
| `sandbox_list_files` | List files in a sandbox directory |
| `run_shell` | Run a shell command in the sandbox |

### ORS Notes (3 tools)
| Tool | Description |
|------|-------------|
| `ors_list_notes` | List ORS notes for a user |
| `ors_add_note` | Add an ORS note |
| `ors_archive_note` | Archive an ORS note |

## Backup Configuration

The backup tools communicate with Clara's API service to manage database backups. Supported destination types:

### S3-Compatible Storage
```json
{
  "bucket": "my-backups",
  "endpoint_url": "https://s3.wasabisys.com",
  "access_key": "...",
  "secret_key": "...",
  "region": "us-east-1"
}
```

### Google Drive
```json
{
  "folder_id": "...",
  "credentials_json": "..."
}
```

### FTP/SFTP
```json
{
  "host": "ftp.example.com",
  "port": 22,
  "username": "...",
  "password": "...",
  "path": "/backups",
  "protocol": "sftp"
}
```

### Schedule Examples
- `0 3 * * *` - Daily at 3:00 AM
- `0 */6 * * *` - Every 6 hours
- `0 0 * * 0` - Weekly on Sunday at midnight

## Integration with Clara

Clara automatically registers this server on startup if the binary is found. The config is stored in `.mcp_servers/clara-tools/config.json`:

```json
{
  "name": "clara-tools",
  "source_type": "local",
  "transport": "stdio",
  "command": "/path/to/clara-mcp-server",
  "enabled": true
}
```

## Development

### Project Structure

```
clara-mcp-server/
├── Cargo.toml          # Dependencies and build config
├── src/
│   ├── main.rs         # Server entry point and tool definitions
│   └── tools/
│       ├── mod.rs      # Tool module exports
│       ├── backup.rs   # Database backup tools
│       ├── claude_code.rs
│       ├── ors_notes.rs
│       └── sandbox.rs
└── target/
    └── release/
        └── clara-mcp-server
```

### Adding New Tools

1. Create a new module in `src/tools/`
2. Export it in `src/tools/mod.rs`
3. Add the tool struct to `ClaraServer` in `main.rs`
4. Implement tool methods with the `#[tool]` macro

Example:
```rust
#[tool(description = "My new tool")]
async fn my_tool(&self, Parameters(p): Parameters<MyParams>) -> Result<CallToolResult, McpError> {
    match self.my_module.do_something(p.arg).await {
        Ok(text) => Ok(CallToolResult::success(vec![Content::text(text)])),
        Err(e) => Ok(CallToolResult::error(vec![Content::text(e)])),
    }
}
```

### Dependencies

- `rmcp` - Rust MCP SDK
- `tokio` - Async runtime
- `reqwest` - HTTP client for API calls
- `sqlx` - Database access (PostgreSQL/SQLite)
- `serde` / `schemars` - Serialization and JSON schema generation

## License

MIT
