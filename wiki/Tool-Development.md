# Tool Development

Guide to creating custom tools for Clara.

## Overview

Clara's tool system provides:
- Dynamic tool loading with hot-reload
- Context passing (user, channel, platform)
- Permission checking
- Type-safe parameters via Pydantic

## Tool Structure

### Basic Tool

```python
# mypalclara/tools/my_tools.py

from mypalclara.core.tool_registry import tool, ToolContext

@tool(
    name="greet_user",
    description="Greet a user by name",
)
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

@tool(
    name="search_files",
    description="Search for files matching criteria",
)
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
@tool(name="admin_action", description="Admin-only action")
async def admin_action(ctx: ToolContext) -> str:
    if not await ctx.is_admin():
        return "Error: Admin permission required"

    # Perform admin action
    return f"Action completed for {ctx.user_id}"
```

## Tool Categories

### Core Tools

Located in `mypalclara/core/core_tools/`:

```
mypalclara/core/core_tools/
├── mcp_management.py   # MCP server management
├── chat_history.py     # Chat history retrieval
└── system_logs.py      # System log access
```

### Platform-Specific Tools

Located in `mypalclara/tools/`:

```
mypalclara/tools/
├── cli_files.py    # CLI file operations
├── cli_shell.py    # CLI shell execution
├── discord/        # Discord-specific tools
└── shared/         # Cross-platform tools
```

## Registering Tools

### Automatic Discovery

Tools in `mypalclara/tools/` are automatically discovered and loaded.

### Manual Registration

```python
from mypalclara.core.tool_registry import ToolRegistry

registry = ToolRegistry()
registry.register(greet_user)
```

## Hot Reload

Enable hot reload for development:

```bash
TOOL_HOT_RELOAD=true
```

Changes to tool files are automatically detected and reloaded.

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

@tool(name="process_data")
async def process_data(
    data: list[str],                              # List of strings
    format: Literal["json", "csv", "xml"],        # Choice
    limit: Optional[int] = None,                  # Optional
    options: dict = Field(default_factory=dict),  # Dict with default
    ctx: ToolContext = None,
) -> dict:
    ...
```

## Error Handling

### Return Errors as Strings

```python
@tool(name="risky_operation")
async def risky_operation(ctx: ToolContext) -> str:
    try:
        result = do_something()
        return f"Success: {result}"
    except ValueError as e:
        return f"Error: Invalid input - {e}"
    except PermissionError:
        return "Error: Permission denied"
```

### Raise Exceptions

```python
from mypalclara.core.tool_registry import ToolError

@tool(name="strict_operation")
async def strict_operation(ctx: ToolContext) -> str:
    if not validate():
        raise ToolError("Validation failed")
    return "Success"
```

## Testing Tools

### Unit Tests

```python
import pytest
from mypalclara.tools.my_tools import greet_user
from mypalclara.core.tool_registry import ToolContext

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

### Integration Tests

```python
@pytest.mark.asyncio
async def test_tool_via_registry():
    registry = ToolRegistry()
    result = await registry.execute(
        "greet_user",
        {"name": "Bob"},
        context={"user_id": "test"},
    )
    assert "Bob" in result
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

## Admin Tools

Tools requiring admin permission:

```python
@tool(
    name="dangerous_operation",
    description="Admin-only dangerous operation",
    admin_only=True,  # Requires admin
)
async def dangerous_operation(ctx: ToolContext) -> str:
    # Context automatically checks admin
    return "Completed"
```

## Tool Metadata

Additional metadata for tools:

```python
@tool(
    name="example_tool",
    description="Example with metadata",
    category="utilities",      # Tool category
    platforms=["discord"],     # Platform restrictions
    rate_limit=10,             # Calls per minute
    hidden=False,              # Show in tool list
)
async def example_tool(ctx: ToolContext) -> str:
    ...
```

## MCP Tool Integration

Tools from MCP servers are automatically namespaced:

```
{server_name}__{tool_name}
```

Example: `github__create_issue`

### Creating MCP-Compatible Tools

```python
@tool(
    name="mcp_compatible",
    mcp_schema={
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"]
        }
    }
)
async def mcp_compatible(query: str, ctx: ToolContext) -> dict:
    return {"results": [...]}
```

## File Structure Example

```
mypalclara/tools/
├── __init__.py
├── utilities/
│   ├── __init__.py
│   ├── text_tools.py      # Text manipulation
│   ├── math_tools.py      # Calculations
│   └── date_tools.py      # Date/time utilities
├── integrations/
│   ├── __init__.py
│   ├── github_tools.py    # GitHub integration
│   └── slack_tools.py     # Slack integration
└── admin/
    ├── __init__.py
    └── system_tools.py    # Admin operations
```

## See Also

- [[MCP-Plugin-System]] - External tool plugins
- [[Architecture]] - System architecture
- [[Configuration]] - Tool configuration
