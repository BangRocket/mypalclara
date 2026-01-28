# Phase 3: CLI Client & Retirement - Research

**Researched:** 2026-01-27
**Domain:** WebSocket client patterns, file deletion safety, single entry point architecture
**Confidence:** HIGH

## Summary

This phase completes the migration to the gateway architecture by:
1. Refactoring cli_bot.py to use the WebSocket gateway instead of direct MemoryManager
2. Safely deleting discord_bot.py and email_monitor.py (5,187 lines total)
3. Establishing python -m gateway as the single entry point
4. Updating documentation and Docker configuration

**Key finding:** The CLI WebSocket client pattern already exists and is proven (adapters/cli/gateway_client.py). The challenge is not technical implementation but safe deletion with verification that all functionality has been migrated to providers.

**Primary recommendation:** Use dependency mapping to verify zero imports of discord_bot.py/email_monitor.py before deletion, then update all references in documentation and Docker.

## Standard Stack

The established libraries/tools for this domain:

### Core WebSocket
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| websockets | 16.0+ | WebSocket client/server | Official Python WebSocket library, asyncio-native, robust reconnection |
| pydantic | 2.x | Message validation | Type-safe protocol parsing, JSON serialization |

### CLI Interaction
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|-------------|
| prompt_toolkit | 3.x | Interactive prompts | Async prompt support, history, autocomplete |
| rich | 13.x | Terminal formatting | Markdown rendering, live updates, panels |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio | stdlib | Event loop | All async operations |
| pathlib | stdlib | Path operations | File system checks, documentation updates |

**Installation:**
All libraries already installed in pyproject.toml. No new dependencies needed.

## Architecture Patterns

### Recommended Project Structure
```
adapters/
├── cli/
│   ├── gateway_client.py   # WebSocket client (EXISTS)
│   ├── main.py             # Entry point (EXISTS)
│   └── adapter.py          # Platform adapter (EXISTS)
├── base.py                 # Base GatewayClient (EXISTS)
└── protocol.py             # Shared protocol (EXISTS)

gateway/
├── __main__.py             # Single entry point
├── main.py                 # Server initialization
└── providers/              # (Phase 2 creates these)

# Files to DELETE:
cli_bot.py                  # 621 lines - direct MemoryManager usage
discord_bot.py              # 4,384 lines - migrated to gateway/providers/discord.py
email_monitor.py            # 803 lines - migrated to gateway/providers/email.py
```

### Pattern 1: WebSocket CLI Client (Already Implemented)

**What:** CLI connects to gateway via WebSocket, receives streaming responses
**When to use:** This phase - refactor cli_bot.py to use existing gateway client
**Example:**
```python
# Source: adapters/cli/gateway_client.py (existing code)
from adapters.cli.gateway_client import CLIGatewayClient

client = CLIGatewayClient(
    console=console,
    user_id=USER_ID,
    gateway_url="ws://127.0.0.1:18789"
)

# Connect to gateway
await client.connect()

# Send message and wait for response
response = await client.send_cli_message(
    content="Hello Clara",
    tier_override="mid"
)
```

The client already handles:
- WebSocket connection with automatic reconnection
- Protocol message parsing
- Live streaming display with Rich
- Tool execution status updates
- Error handling

### Pattern 2: Safe File Deletion

**What:** Verify zero dependencies before deleting legacy files
**When to use:** Before `git rm` commands
**Example:**
```python
# Dependency check strategy:
# 1. Grep for imports
grep -r "^from discord_bot import\|^import discord_bot" . --include="*.py"
# Should return: No files found (or only discord_bot.py itself)

# 2. Grep for documentation references
grep -r "discord_bot\.py" . --include="*.md" --include="*.yml"
# Update all found files

# 3. Check Docker Compose
grep "discord_bot" docker-compose.yml
# Update or remove service definitions

# 4. Only then delete
git rm discord_bot.py email_monitor.py cli_bot.py
```

### Pattern 3: Single Entry Point Architecture

**What:** All platform providers start from `python -m gateway`
**When to use:** Post-migration unified deployment
**Example:**
```python
# gateway/__main__.py (existing pattern)
from gateway.main import main, parse_args

if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args.host, args.port, args.hooks_dir, args.scheduler_dir))
```

Each provider auto-starts within the gateway process:
- Discord provider: Connects discord.py bot to gateway processor
- Email provider: Background monitoring loop, sends to gateway
- CLI provider: External process connects via WebSocket (optional)

### Anti-Patterns to Avoid

- **Deleting files before verifying migration:** Check imports first, ensure providers have feature parity
- **Breaking backward compatibility:** Old CLI users might run `python cli_bot.py` - provide clear migration message
- **Forgetting documentation:** README.md, CLAUDE.md, docker-compose.yml all reference old files
- **Not testing WebSocket connection:** Ensure gateway is running before CLI client attempts connection

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WebSocket reconnection | Custom backoff logic | GatewayClient.auto_reconnect | Already implements exponential backoff, session preservation |
| CLI streaming display | Manual text updates | Live + Markdown from Rich | Handles markdown rendering, refresh rate, terminal size |
| Message protocol parsing | JSON dict access | pydantic models (gateway.protocol) | Type safety, validation, serialization |
| Dependency detection | Manual file scanning | grep with strict patterns | Fast, reliable, used in industry |

**Key insight:** The CLI gateway client (adapters/cli/gateway_client.py) already exists and works. The task is refactoring cli_bot.py to use it, not building a new client.

## Common Pitfalls

### Pitfall 1: Deleting discord_bot.py While Still Imported

**What goes wrong:** Runtime ImportError when other modules try to import from deleted file
**Why it happens:** email_monitor.py imports from discord_bot, not checking full dependency tree
**How to avoid:**
1. Run: `grep -r "from discord_bot import\|import discord_bot" . --include="*.py"`
2. Verify only discord_bot.py itself shows up (self-reference)
3. Check email_monitor.py line 106: imports discord bot reference
4. Ensure Phase 2 moved email_monitor to gateway/providers/email.py first
**Warning signs:**
- `grep` shows files other than discord_bot.py
- Phase 2 not marked complete
- Test imports fail

### Pitfall 2: Breaking Old CLI Entry Point

**What goes wrong:** Users run `poetry run python cli_bot.py` and get connection refused
**Why it happens:** Deleting cli_bot.py without migration path or warning
**How to avoid:**
1. Keep cli_bot.py as a stub that prints migration message
2. Or update pyproject.toml scripts to point to `python -m adapters.cli`
3. Update README.md with new command: `poetry run python -m adapters.cli`
**Warning signs:**
- Direct execution of deleted file path in docs
- No migration notice for existing users
- Scripts hardcode old path

### Pitfall 3: Docker Compose Inconsistency

**What goes wrong:** Docker still tries to run discord-bot service with deleted discord_bot.py
**Why it happens:** docker-compose.yml not updated to use gateway-only architecture
**How to avoid:**
1. Review docker-compose.yml services
2. Remove discord-bot service (or point to gateway)
3. Ensure gateway service has all necessary env vars for Discord/Email providers
4. Test: `docker-compose --profile gateway up`
**Warning signs:**
- Build fails looking for discord_bot.py
- Two separate services (gateway + discord-bot) running in parallel
- Missing environment variables on gateway service

### Pitfall 4: Documentation Drift

**What goes wrong:** README.md still says "poetry run python discord_bot.py"
**Why it happens:** Forgetting to update all documentation after file deletion
**How to avoid:**
1. Search all docs: `grep -r "discord_bot\|email_monitor\|cli_bot" . --include="*.md"`
2. Update README.md "Running" section
3. Update CLAUDE.md "Development Commands" section
4. Update any migration guides or tutorials
**Warning signs:**
- Docs show commands that fail
- Users follow outdated instructions
- Support requests about missing files

## Code Examples

Verified patterns from the codebase:

### Refactored CLI Entry Point
```python
# Source: adapters/cli/main.py (existing, proven pattern)
from adapters.cli.gateway_client import CLIGatewayClient
from prompt_toolkit import PromptSession
from rich.console import Console

async def main() -> None:
    console = Console()

    # Create gateway client (not MemoryManager)
    client = CLIGatewayClient(
        console=console,
        user_id="cli-user",
        gateway_url="ws://127.0.0.1:18789"
    )

    # Connect to gateway
    if not await client.connect():
        console.print("[red]Failed to connect[/red]")
        return

    # REPL loop
    session = PromptSession(history=FileHistory("~/.clara_cli_history"))
    while True:
        user_input = await session.prompt_async("You: ")
        response = await client.send_cli_message(user_input)
        console.print(response)
```

This pattern already works. The task is removing the old cli_bot.py code and ensuring all entry points use this.

### Safe Deletion Verification Script
```bash
# Check for discord_bot.py imports
echo "Checking discord_bot.py dependencies..."
DISCORD_IMPORTS=$(grep -r "from discord_bot import\|import discord_bot" . --include="*.py" | grep -v "^discord_bot.py:")
if [ -n "$DISCORD_IMPORTS" ]; then
    echo "ERROR: Found imports:"
    echo "$DISCORD_IMPORTS"
    exit 1
fi

# Check for email_monitor.py imports
echo "Checking email_monitor.py dependencies..."
EMAIL_IMPORTS=$(grep -r "from email_monitor import\|import email_monitor" . --include="*.py" | grep -v "^email_monitor.py:")
if [ -n "$EMAIL_IMPORTS" ]; then
    echo "ERROR: Found imports:"
    echo "$EMAIL_IMPORTS"
    exit 1
fi

# Check documentation references
echo "Checking documentation references..."
DOC_REFS=$(grep -l "discord_bot\.py\|email_monitor\.py\|cli_bot\.py" *.md docker-compose.yml 2>/dev/null)
if [ -n "$DOC_REFS" ]; then
    echo "WARNING: Found documentation references:"
    echo "$DOC_REFS"
    echo "Update these files before deleting"
fi

echo "✓ Safe to delete"
```

### Gateway Single Entry Point
```python
# Source: gateway/__main__.py (existing)
from gateway.main import main, parse_args

if __name__ == "__main__":
    import asyncio

    args = parse_args()
    try:
        asyncio.run(main(args.host, args.port, args.hooks_dir, args.scheduler_dir))
    except KeyboardInterrupt:
        pass
```

This is already the entry point. The task is ensuring docs reflect this as the primary way to run Clara.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| cli_bot.py with direct MemoryManager | CLI WebSocket client | This phase | Unified architecture, consistent with Discord/Email |
| Three separate entry points | Single gateway entry | This phase | Simpler deployment, easier to maintain |
| discord_bot.py standalone | gateway/providers/discord.py | Phase 2 | Legacy file can be deleted |
| email_monitor.py standalone | gateway/providers/email.py | Phase 2 | Legacy file can be deleted |

**Deprecated/outdated:**
- `cli_bot.py`: Direct MemoryManager access - use WebSocket client instead
- `discord_bot.py`: Standalone entry point - functionality moved to gateway provider
- `email_monitor.py`: Direct Discord bot reference - moved to gateway provider
- Multiple Docker services: Use single gateway service with all providers

## Open Questions

Things that couldn't be fully resolved:

1. **Should cli_bot.py be stubbed or deleted completely?**
   - What we know: Deleting breaks backward compatibility for users
   - What's unclear: How many users invoke it directly vs via scripts
   - Recommendation: Keep as stub with migration message for 1 version, then delete

2. **Should Docker Compose remove discord-bot service entirely?**
   - What we know: Gateway service can run Discord provider
   - What's unclear: Railway/production deployments might expect separate services
   - Recommendation: Keep both service definitions initially, mark discord-bot as deprecated

3. **What if Phase 2 (providers) isn't complete?**
   - What we know: Can't delete discord_bot.py if providers don't exist
   - What's unclear: Partial migration state if Phase 2 blocked
   - Recommendation: Make Phase 2 completion a hard prerequisite, block Phase 3 if not done

## Sources

### Primary (HIGH confidence)
- Existing codebase:
  - `adapters/cli/gateway_client.py` - Proven WebSocket client implementation
  - `adapters/base.py` - GatewayClient base class with reconnection
  - `gateway/protocol.py` - Protocol message types
  - `gateway/__main__.py` - Single entry point pattern
  - `discord_bot.py` line 106-112 - email_monitor import dependency
  - `docker-compose.yml` - Current service definitions

### Secondary (MEDIUM confidence)
- [Python WebSocket Implementation | WebSocket.org](https://websocket.org/guides/languages/python/) - Standard patterns
- [websockets 16.0 documentation](https://websockets.readthedocs.io/) - Official library docs
- [Client (asyncio) - websockets documentation](https://websockets.readthedocs.io/en/stable/reference/asyncio/client.html) - Reconnection patterns

### Tertiary (LOW confidence)
- [WebSockets and AsyncIO: Beyond 5-line Samples](https://betterprogramming.pub/websockets-and-asyncio-beyond-5-line-samples-part-1-ddf8699a18ce) - Advanced patterns (not needed, basics sufficient)

## Metadata

**Confidence breakdown:**
- WebSocket client pattern: HIGH - existing code already works (adapters/cli/gateway_client.py)
- Safe deletion strategy: HIGH - grep-based dependency checking is standard practice
- Single entry point: HIGH - gateway/__main__.py already exists and proven
- Documentation updates: HIGH - clear file list, grep patterns identify all references

**Research date:** 2026-01-27
**Valid until:** 2026-02-27 (30 days - stable architecture patterns)

**Dependencies verified:**
- Phase 2 must be complete (providers exist)
- Gateway server operational
- WebSocket protocol stable (gateway.protocol)
- No runtime imports of discord_bot.py or email_monitor.py

**Migration safety checklist:**
- [ ] Phase 2 providers tested and working
- [ ] Zero imports found via grep for discord_bot/email_monitor
- [ ] Documentation updated (README.md, CLAUDE.md)
- [ ] Docker Compose updated or deprecated services marked
- [ ] CLI client tested against running gateway
- [ ] Backward compatibility plan (stub or error message)
