# Clara Gateway Consolidation

## What This Is

Consolidating MyPalClara into a single gateway daemon architecture. The gateway becomes THE runtime — Discord, Email, and other providers run as internal components, while CLI and Web clients connect via WebSocket. This replaces the current dual-process model (discord_bot.py + gateway) with a unified `python -m gateway` entry point.

## Core Value

**Single daemon, multiple providers.** All Clara functionality runs from one process. Adding a new platform (Slack, Telegram) means creating one provider file — the gateway handles the rest.

## Requirements

### Validated

<!-- Existing capabilities from current codebase that must continue working -->

- ✓ Discord bot responds to messages with streaming LLM responses — existing
- ✓ Memory system (mem0) provides context from past conversations — existing
- ✓ MCP plugins extend Clara with external tools — existing
- ✓ Code execution via Docker/Incus sandbox — existing
- ✓ Email monitoring with rule-based alerts — existing
- ✓ Hooks and scheduler trigger on events — existing
- ✓ Multi-model tier support (!high, !mid, !low) — existing
- ✓ Image/vision support in Discord — existing

### Active

<!-- What we're building in this milestone -->

- [ ] Gateway daemon runs all providers from single process
- [ ] Discord provider integrated into gateway (not separate process)
- [ ] Email provider integrated into gateway
- [ ] CLI client connects to gateway via WebSocket
- [ ] `python -m gateway` is the only entry point needed
- [ ] `discord_bot.py` deleted (code merged into gateway)
- [ ] Provider architecture supports adding Slack/Telegram later

### Out of Scope

- Slack provider implementation — architecture only, defer actual Slack to future milestone
- Telegram provider implementation — same, architecture only
- Web UI client — gateway supports it, but building UI is separate work
- Changes to mem0 storage — databases must remain untouched

## Context

**Current state:** Discord functionality lives in `discord_bot.py` (~3700 lines), duplicating logic that also exists in the gateway. The gateway was built for "future adapters" but Discord still runs separately.

**Pain:** Two processes to run, code duplication, changes require updating both places.

**Architecture inspiration:** Moltbot-style single daemon with providers managed internally.

**Codebase mapping:** See `.planning/codebase/` for detailed analysis of existing code, conventions, and concerns.

## Constraints

- **Data preservation**: mem0 databases must not be modified or corrupted
- **Deployment**: Bare metal via `poetry run` — no Docker/Railway dependencies
- **Python**: Continue using py-cord for Discord, existing LLM backends

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Providers run inside gateway (not as WS clients) | Reduces latency, simplifies deployment | — Pending |
| Delete discord_bot.py completely | Clean break over strangler fig | — Pending |
| CLI connects via WebSocket | Consistent client interface | — Pending |

---
*Last updated: 2026-01-27 after initialization*
