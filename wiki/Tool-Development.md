# Tool Development

Guide to creating custom tools for Clara.

## Overview

Clara's tool system provides:
- Plugin-based tool loading
- Context passing (user, channel, platform)
- Permission checking
- Type-safe parameters via Pydantic

## Tool Structure

### Basic Tool

```python
# clara_core/core_tools/my_tool.py

from tools import ToolContext

async def greet_user(name: str, ctx: ToolContext) -> str:
    """
    Greet a user warmly.

    Args:
        name: The name of the person to greet
    """
    return f"Hello, {name}! Nice to meet you."
```

### Tool with Complex Parameters

```python
from typing import Optional
from pydantic import Field

async def search_files(
    pattern: str = Field(description="File pattern to match"),
    directory: str = Field(default=".", description="Directory to search"),
    recursive: bool = Field(default=True, description="Search subdirectories"),
    ctx: ToolContext = None,
) -> dict:
    """Search for files matching a pattern."""
    # Implementation
    return {"files": [...], "count": 10}
```

## Tool Context

The `ToolContext` object provides:

```python
class ToolContext:
    user_id: str          # User identifier
    channel_id: str       # Channel/conversation ID
    platform: str         # "discord", "teams", "cli"
    extra: dict           # Platform-specific data

    # Methods
    async def is_admin(self) -> bool
    async def get_user_data(self, key: str) -> Any
    async def set_user_data(self, key: str, value: Any)
```

### Using Context

```python
async def admin_action(ctx: ToolContext) -> str:
    if not await ctx.is_admin():
        return "Error: Admin permission required"

    # Perform admin action
    return f"Action completed for {ctx.user_id}"
```

## Tool Categories

### Core Tools

Located in `clara_core/core_tools/`:

```
clara_core/core_tools/
├── browser_tool.py     # Playwright browser automation
├── chat_history.py     # Chat history retrieval
├── files_tool.py       # File operations
├── mcp_management.py   # MCP server management
├── process_tool.py     # Background process management
├── system_logs.py      # System log access
└── terminal_tool.py    # Terminal/shell execution
```

### Tool Infrastructure

Located in `tools/`:

```
tools/
├── _base.py       # Base tool definitions
├── _loader.py     # Dynamic tool loading
└── _registry.py   # Tool registry (wraps clara_core/plugins/)
```

## Plugin System

Tools are loaded through the plugin system in `clara_core/plugins/`:

```
clara_core/plugins/
├── loader.py       # Plugin discovery and loading
├── registry.py     # Plugin registration
├── runtime.py      # Plugin execution runtime
├── manifest.py     # Plugin manifests
├── policies.py     # Security policies
├── audit.py        # Security audit
└── hooks.py        # Plugin hooks
```

The `tools/_registry.py` provides a backwards-compatible `ToolRegistry` wrapper around the plugin system.

## Parameter Types

### Supported Types

| Type | Description |
|------|-------------|
| `str` | String parameter |
| `int` | Integer parameter |
| `float` | Float parameter |
| `bool` | Boolean parameter |
| `list` | List of items |
| `dict` | Dictionary/object |
| `Optional[T]` | Optional parameter |
| `Literal[...]` | Enum-like choices |

### Examples

```python
from typing import Literal, Optional

async def process_data(
    data: list[str],                              # List of strings
    format: Literal["json", "csv", "xml"],        # Choice
    limit: Optional[int] = None,                  # Optional
    options: dict = Field(default_factory=dict),   # Dict with default
    ctx: ToolContext = None,
) -> dict:
    ...
```

## Error Handling

### Return Errors as Strings

```python
async def risky_operation(ctx: ToolContext) -> str:
    try:
        result = do_something()
        return f"Success: {result}"
    except ValueError as e:
        return f"Error: Invalid input - {e}"
    except PermissionError:
        return "Error: Permission denied"
```

## Testing Tools

### Unit Tests

```python
import pytest
from tools import ToolContext

@pytest.mark.asyncio
async def test_greet_user():
    ctx = ToolContext(
        user_id="test-user",
        channel_id="test-channel",
        platform="test",
    )
    result = await greet_user("Alice", ctx=ctx)
    assert "Alice" in result
```

## Best Practices

### Do

- Use descriptive names and descriptions
- Validate inputs early
- Return helpful error messages
- Use type hints
- Document parameters with Field descriptions
- Handle exceptions gracefully

### Don't

- Expose sensitive operations without auth checks
- Return raw exceptions to users
- Block for long periods (use async)
- Modify global state without synchronization

## MCP Tool Integration

Tools from MCP servers are automatically namespaced:

```
{server_name}__{tool_name}
```

Example: `github__create_issue`, `filesystem__read_file`

MCP tools are managed via the MCP system in `clara_core/mcp/`. See [[MCP-Plugin-System]] for details on installing and managing MCP servers.

## See Also

- [[MCP-Plugin-System]] - External tool plugins
- [[Architecture]] - System architecture
- [[Configuration]] - Tool configuration
