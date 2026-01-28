# Clara Gateway Consolidation

## What This Is

MyPalClara — a personal AI assistant with unified gateway architecture. Discord, Email, and CLI all run as internal providers from a single `python -m gateway` entry point. The gateway handles lifecycle management, message routing, and provider coordination.

## Core Value

**Single daemon, multiple providers.** All Clara functionality runs from one process. Adding a new platform (Slack, Telegram) means creating one provider file — the gateway handles the rest.

## Requirements

### Validated

- ✓ Gateway daemon runs all providers from single process — v2026.05.109
- ✓ Provider lifecycle management (start, stop, restart) — v2026.05.109
- ✓ Discord provider integrated via Strangler Fig pattern — v2026.05.109
- ✓ Email provider with event-based alerts to Discord — v2026.05.109
- ✓ CLI client connects via WebSocket — v2026.05.109
- ✓ `python -m gateway` is the only entry point needed — v2026.05.109
- ✓ Protocol versioning for adapter compatibility — v2026.05.109
- ✓ Provider architecture supports adding Slack/Telegram — v2026.05.109
- ✓ Discord streaming LLM responses — v2026.05.109
- ✓ Discord message queuing and batching — v2026.05.109
- ✓ Discord multi-model tier selection (!high, !mid, !low) — v2026.05.109
- ✓ Discord image/vision capabilities — v2026.05.109
- ✓ Discord reply chain tracking — v2026.05.109
- ✓ Email monitoring with rule-based alerts — v2026.05.109
- ✓ email_monitor.py deleted (code migrated to adapters/email/) — v2026.05.109
- ✓ mem0 databases untouched and functional — v2026.05.109
- ✓ Session history continues working — v2026.05.109
- ✓ Memory system (mem0) provides context — v2026.05.109
- ✓ MCP plugins extend Clara — v2026.05.109
- ✓ Code execution via sandbox — v2026.05.109
- ✓ Hooks and scheduler trigger on events — v2026.05.109
- ✓ Behavioral tests pass (message dedup, emotional context) — v2026.05.109
- ✓ Provider crash triggers auto-restart — v2026.05.109
- ✓ Rate limiting prevents spam — v2026.05.109
- ✓ Health check endpoint reports status — v2026.05.109
- ✓ Structured logging includes context — v2026.05.109
- ✓ Gateway handles 100+ concurrent users — v2026.05.109
- ✓ Graceful shutdown completes pending responses — v2026.05.109
- ✓ Modern websockets API (no deprecation warnings) — v2026.05.109

### Active

(None — milestone complete, fresh requirements needed for next milestone)

### Out of Scope

- Slack provider implementation — architecture ready, implementation deferred
- Telegram provider implementation — architecture ready, implementation deferred
- Web UI client — gateway supports it, building UI is separate work
- Changes to mem0 storage — databases remain untouched
- Active-mode batching optimization — defer to v2
- DiscordProvider standalone refactor — Strangler Fig is permanent architecture

## Context

**Current state:** Shipped v2026.05.109 Gateway Unification.

**Tech stack:** Python 3.12, py-cord, websockets 13+, mem0, PostgreSQL/SQLite, Qdrant/pgvector.

**Architecture:** Single gateway daemon with DiscordProvider (wraps discord_bot.py), EmailProvider, and CLI client. Providers run in-process for low latency.

**Codebase:** ~24k LOC Python. 121 files modified in v1 milestone. 171 tests passing.

## Constraints

- **Data preservation**: mem0 databases must not be modified or corrupted
- **Deployment**: Bare metal via `poetry run` — no Docker/Railway dependencies required
- **Python**: Continue using py-cord for Discord, existing LLM backends
- **Architecture**: Strangler Fig pattern for DiscordProvider is permanent (no rewrite)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Providers run inside gateway (not as WS clients) | Reduces latency, simplifies deployment | ✓ Good |
| Strangler Fig for Discord | Preserves 4,384 lines without rewrite, low risk | ✓ Good |
| Keep discord_bot.py wrapped (not deleted) | DiscordProvider composition is permanent architecture | ✓ Good |
| CLI connects via WebSocket | Consistent client interface | ✓ Good |
| Protocol versioning from Phase 1 | Prevents future breaking changes | ✓ Good |
| Behavioral tests before extraction | Catches lost features early | ✓ Good |
| Rate limiting per user/channel | Prevents spam without blocking legitimate use | ✓ Good |
| Health checks on separate port (18790) | Avoids conflicts, enables K8s probes | ✓ Good |
| Modern websockets asyncio API | No deprecation warnings, forward compatible | ✓ Good |

---
*Last updated: 2026-01-28 after v2026.05.109 milestone*
