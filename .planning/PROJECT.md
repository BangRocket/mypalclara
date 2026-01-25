# MyPalClara Platform Refactor

## What This Is

Refactoring MyPalClara to separate the core AI assistant functionality (memory, personality, LLM, tools, MCP) from platform-specific code (Discord), enabling multiple input interfaces. The first new interface is a CLI that provides a Claude Code-like terminal experience with Clara's personality and shared memory.

## Core Value

Clara works identically across any interface — same personality, same memory, same capabilities — with platform-appropriate presentation.

## Requirements

### Validated

*Existing capabilities from the current codebase:*

- ✓ LLM provider abstraction (OpenRouter, NanoGPT, OpenAI, Anthropic) — existing
- ✓ Session-based conversation management — existing
- ✓ mem0 semantic memory integration — existing
- ✓ Tool registry with async execution — existing
- ✓ MCP plugin system for extensible tools — existing
- ✓ Discord bot with streaming responses — existing
- ✓ Code sandbox execution (Docker/remote) — existing
- ✓ File storage (local/S3) — existing
- ✓ Personality and persona system — existing
- ✓ Model tier selection (high/mid/low) — existing
- ✓ Skills system — existing

### Active

*New capabilities for this milestone:*

- [ ] Platform-agnostic core that any interface can use
- [ ] Abstract "channel" concept (Discord channels, DMs, CLI sessions)
- [ ] CLI interface with REPL-style chat
- [ ] CLI streaming output (like Claude Code)
- [ ] CLI file read/write tools
- [ ] CLI shell command execution
- [ ] CLI MCP server access
- [ ] CLI Skills support
- [ ] Shared user memory across all platforms
- [ ] Separate conversation context per channel/session

### Out of Scope

- Web UI — future milestone, not this one
- Slack integration — future milestone
- Mobile app — no plans
- Multi-user CLI — personal use only
- Breaking Discord functionality — must remain fully operational

## Context

**Current architecture has partial abstraction:**
- `clara_core/` exists with `MemoryManager`, `ToolRegistry`, `PlatformAdapter`
- `PlatformAdapter` base class exists but Discord implementation is tangled in 4,391-line `discord_bot.py`
- Some tools are Discord-specific (send embeds, reactions) vs platform-agnostic

**The refactor challenge:**
- Extract truly platform-agnostic core from `discord_bot.py`
- Make `PlatformAdapter` a real abstraction that CLI can implement
- Handle platform-specific tool variants (e.g., file sending works differently in CLI vs Discord)

**CLI goals:**
- Feel like Claude Code but with Clara's personality
- File operations and shell commands for coding tasks
- Same mem0 memories as Discord Clara
- CLI sessions are just another "channel" in the system

## Constraints

- **Backwards compatibility**: Discord bot must continue working throughout refactor
- **Same codebase**: CLI and Discord share one repo, one core
- **Personal use**: CLI is for owner only, no auth/multi-user complexity
- **Python stack**: Continue using Python 3.11+, Poetry, existing dependencies

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| CLI as first new platform | Simplest to implement, immediate personal value | — Pending |
| Shared memory, separate conversations | Matches current Discord channel behavior | — Pending |
| Streaming output for CLI | Matches Claude Code UX, better experience | — Pending |

---
*Last updated: 2026-01-24 after initialization*
