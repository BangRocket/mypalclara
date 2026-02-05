# CLI Adapter

Interactive terminal interface for Clara.

## Overview

The CLI adapter provides a rich terminal interface for interacting with Clara:
- Interactive prompt with command history
- Markdown rendering for responses
- Shell command execution with approval flow
- Model tier selection
- File operations

## Running

### Standalone

```bash
poetry run python -m adapters.cli
```

### With Gateway

```bash
# Terminal 1: Start gateway
poetry run python -m mypalclara.gateway

# Terminal 2: Start CLI
poetry run python -m adapters.cli
```

## Configuration

```bash
# Gateway connection
CLARA_GATEWAY_URL=ws://127.0.0.1:18789    # Gateway WebSocket URL

# User identification
CLI_USER_ID=cli-user                       # User identifier for sessions
```

## Features

### Interactive Prompt

```
clara> Hello, how are you?
Clara: I'm doing well! How can I help you today?

clara> !high Explain quantum entanglement
Clara: [Uses high-tier model for response]

clara> /quit
Goodbye!
```

### Model Tiers

Prefix messages to select model tier:

| Prefix | Tier |
|--------|------|
| `!high` or `!opus` | High (Opus-class) |
| `!mid` or `!sonnet` | Mid (Sonnet-class) |
| `!low` or `!haiku` | Low (Haiku-class) |

### Shell Execution

Clara can execute shell commands with user approval:

```
clara> List files in my home directory

Clara: I'll list the files in your home directory.

[Shell Command Approval]
Command: ls -la ~
Allow? [y/n]: y

[Output displayed]
```

### Commands

| Command | Description |
|---------|-------------|
| `/quit` or `/exit` | Exit CLI |
| `/clear` | Clear conversation |
| `/history` | Show command history |
| `/help` | Show help |

### Command History

History is stored in `~/.clara_cli_history` and persists across sessions.

Use arrow keys to navigate previous commands.

## File Operations

The CLI adapter supports file operations within your configured directories:

- Read files
- Write files
- List directories
- Execute scripts

## Architecture

```
Terminal Input
      │
      ▼
┌─────────────────┐
│   CLI Adapter   │  (adapters/cli/)
│    main.py      │
└────────┬────────┘
         │ WebSocket
         ▼
┌─────────────────┐
│    Gateway      │  Message processing, tools, memory
└─────────────────┘
```

## File Structure

```
adapters/cli/
├── __init__.py
├── main.py           # Entry point and REPL
├── adapter.py        # CLI adapter implementation
├── gateway_client.py # Gateway WebSocket client
├── shell_executor.py # Shell command handling
└── approval.py       # User approval system
```

## Use Cases

### Development Testing

Test Clara's responses and tools without Discord:

```bash
poetry run python -m adapters.cli
```

### Scripting

Pipe commands to Clara:

```bash
echo "What is 2+2?" | poetry run python -m adapters.cli --no-interactive
```

### Server Administration

Use Clara for system administration tasks with shell execution approval.

## See Also

- [[Gateway]] - Gateway server documentation
- [[Discord-Features]] - Discord interface
- [[Teams-Adapter]] - Teams interface
