# Gateway Consolidation Roadmap

**Project:** MyPalClara Gateway Architecture Consolidation
**Milestone:** Gateway Unification v1
**Created:** 2026-01-27
**Status:** Planning Complete

---

## Overview

Consolidate MyPalClara into a single gateway daemon architecture where Discord, Email, and CLI run as internal provider components. This replaces the current dual-process model (discord_bot.py + gateway) with a unified `python -m gateway` entry point.

**Core Value:** Single daemon, multiple providers. Adding a new platform means creating one provider file — the gateway handles the rest.

**Depth:** Quick (3-5 phases, consolidated from research recommendations)
**Mode:** YOLO (no phase-by-phase approval)

---

## Phases

### Phase 1: Provider Foundation

**Goal:** Establish provider abstraction layer and migrate Discord to run inside gateway process.

**Dependencies:** None (starting phase)

**Requirements Coverage:**
- Gateway daemon runs all providers from single process
- Discord provider integrated into gateway (not separate process)
- Provider architecture supports adding Slack/Telegram later

**Deliverables:**
1. `Provider` abstract base class with lifecycle methods (start, stop, normalize_message, send_response)
2. `ProviderManager` singleton for lifecycle management
3. `PlatformMessage` dataclass for normalized message format
4. `DiscordProvider` wrapping existing discord_bot.py logic (Strangler Fig pattern)
5. Gateway startup modified to initialize ProviderManager
6. Protocol versioning (v1.0) in all WebSocket messages

**Success Criteria:**
- [ ] Provider base class defines clear interface (start, stop, normalize_message, send_response)
- [ ] DiscordProvider wraps discord_bot.py code without rewriting core logic
- [ ] Gateway can start/stop DiscordProvider programmatically
- [ ] Discord messages flow through Provider.normalize_message() to PlatformMessage
- [ ] Protocol version field present in all gateway messages
- [ ] No behavioral regression: Discord bot responds identically to before

**Key Risks Mitigated:**
- Lost Stateful Features: Wrapping (not rewriting) preserves all Discord bot behaviors
- Protocol Versioning Naivety: Build versioning from day one
- Incomplete Code Retirement: Clear provider interface enables clean discord_bot.py deletion later

**Files Changed:**
- NEW: `gateway/providers/__init__.py` - Provider base class + ProviderManager
- NEW: `gateway/providers/discord.py` - DiscordProvider wrapper
- MODIFIED: `gateway/main.py` - Initialize ProviderManager, start Discord provider
- MODIFIED: `gateway/protocol.py` - Add protocol_version field to messages
- MODIFIED: `discord_bot.py` - Refactor to support Provider wrapper (temporary, deleted in Phase 3)

**Technical Notes:**
- Use composition over inheritance: DiscordProvider wraps discord.py Client instance
- Discord event handlers delegate to Provider methods
- Message queue/batching logic moves inside DiscordProvider
- Tier selection (!high, !mid, !low) preserved in DiscordProvider

---

### Phase 2: Gateway Integration & Email Provider

**Goal:** Integrate DiscordProvider with gateway core and extract email monitoring as EmailProvider.

**Dependencies:** Phase 1 (requires Provider abstraction)

**Requirements Coverage:**
- Email provider integrated into gateway
- Gateway daemon runs all providers from single process (continued)

**Deliverables:**
1. DiscordProvider connected to MessageProcessor pipeline
2. Response callbacks implemented (response_start, tool_start, tool_result, response_chunk, response_end)
3. `EmailProvider` extracted from email_monitor.py
4. EmailProvider lifecycle managed by ProviderManager
5. Email alerts routed through gateway event system
6. Behavioral test suite validating Discord parity (20+ tests)

**Success Criteria:**
- [ ] Discord message -> Gateway processor -> LLM -> Response flows end-to-end
- [ ] DiscordProvider receives response callbacks and streams to Discord channels
- [ ] Tier-based model selection works (!high, !mid, !low prefixes)
- [ ] Image/vision support functional through DiscordProvider
- [ ] EmailProvider polls accounts and sends alerts via Discord provider
- [ ] All 20+ behavioral tests pass (message dedup, queue batching, emotional context)
- [ ] mem0 databases untouched and functional

**Key Risks Mitigated:**
- Gateway Bottleneck: Stateless design with session state in PostgreSQL
- Silent Regression: Behavioral test suite catches lost features
- Monitoring Blindness: Structured logging + alerts implemented

**Files Changed:**
- MODIFIED: `gateway/providers/discord.py` - Connect to MessageProcessor
- NEW: `gateway/providers/email.py` - EmailProvider wrapping email_monitor.py
- MODIFIED: `gateway/processor.py` - Add provider callback hooks
- MODIFIED: `gateway/main.py` - Start both Discord and Email providers
- NEW: `tests/gateway/test_discord_provider.py` - Behavioral tests
- MODIFIED: `email_monitor.py` - Refactor for Provider wrapper (temporary, deleted in Phase 3)

**Technical Notes:**
- MessageProcessor gets provider_callbacks parameter for response streaming
- EmailProvider uses gateway event system to trigger Discord alerts
- Connection pooling for database/mem0 queries
- ThreadPoolExecutor for blocking I/O (email IMAP)

---

### Phase 3: CLI Client & Retirement

**Goal:** Build WebSocket CLI client, delete discord_bot.py and email_monitor.py completely, establish single entry point.

**Dependencies:** Phase 2 (requires working providers)

**Requirements Coverage:**
- CLI client connects to gateway via WebSocket
- `python -m gateway` is the only entry point needed
- `discord_bot.py` deleted (code merged into gateway)

**Plans:** 3 plans

Plans:
- [ ] 03-01-PLAN.md — Refactor cli_bot.py to migration wrapper, add clara-cli script
- [ ] 03-02-PLAN.md — Verify Phase 2 providers exist and deletion is safe
- [ ] 03-03-PLAN.md — Delete legacy files, update Docker Compose and documentation

**Deliverables:**
1. CLI client refactored to connect via WebSocket (not direct MemoryManager)
2. `cli_bot.py` entry point calls gateway CLI client
3. `discord_bot.py` deleted (all code moved to gateway/providers/discord.py)
4. `email_monitor.py` deleted (all code moved to gateway/providers/email.py)
5. `poetry run python -m gateway` starts all providers
6. Documentation updated (CLAUDE.md, README.md)
7. Docker Compose updated to single gateway service

**Success Criteria:**
- [ ] CLI client connects to gateway WebSocket server
- [ ] CLI messages flow through gateway processor with full tool support
- [ ] `discord_bot.py` deleted from repository (git rm)
- [ ] `email_monitor.py` deleted from repository (git rm)
- [ ] `python -m gateway` starts Discord, Email, and CLI providers
- [ ] No import errors or broken references after deletion
- [ ] docker-compose.yml runs single gateway container
- [ ] All integration tests pass

**Key Risks Mitigated:**
- Incomplete Code Retirement: Explicit deletion phase with completion criteria
- Feature Flag Sprawl: No feature flags needed, clean break

**Files Changed:**
- MODIFIED: `cli_bot.py` - Use WebSocket client instead of direct calls
- NEW: `gateway/providers/cli.py` - CLI provider for local terminal
- DELETED: `discord_bot.py` - 4384 lines moved to gateway/providers/discord.py
- DELETED: `email_monitor.py` - Logic moved to gateway/providers/email.py
- MODIFIED: `gateway/main.py` - Start all three providers
- MODIFIED: `docker-compose.yml` - Single gateway service
- MODIFIED: `CLAUDE.md` - Update deployment instructions
- MODIFIED: `README.md` - Update architecture documentation

**Technical Notes:**
- CLI provider runs in-process (no WebSocket for local mode)
- CLI WebSocket client used only when connecting to remote gateway
- Gateway determines local vs remote CLI based on connection source
- Auto-migration runs on gateway startup (same as before)

---

### Phase 4: Production Hardening

**Goal:** Add monitoring, error recovery, and load validation to ensure production readiness.

**Dependencies:** Phase 3 (requires complete system)

**Requirements Coverage:**
- All validated requirements continue working (mem0, MCP plugins, sandbox, hooks, streaming, etc.)

**Deliverables:**
1. Error recovery for provider crashes (auto-restart with backoff)
2. Rate limiting per user/channel
3. Gateway health check endpoint
4. Structured logging with provider context
5. Resource limits per provider (memory, CPU)
6. Load testing validation (100+ concurrent users)
7. Graceful shutdown with pending message completion
8. Monitoring dashboard updates (if Discord monitor exists)

**Success Criteria:**
- [ ] Provider crash triggers auto-restart (not gateway crash)
- [ ] Rate limits prevent spam (configurable per provider)
- [ ] `/health` endpoint reports gateway + provider status
- [ ] Logs include provider_name, user_id, channel_id context
- [ ] Gateway handles 100+ concurrent users without degradation
- [ ] Graceful shutdown completes pending responses before exit
- [ ] Memory usage stable under sustained load
- [ ] All existing features functional (Discord streaming, MCP tools, sandbox, image vision, email alerts)

**Key Risks Mitigated:**
- Gateway Bottleneck: Load testing validates assumptions
- Monitoring Blindness: Health checks and structured logging
- Single Point of Failure: Provider isolation prevents cascading failures

**Files Changed:**
- MODIFIED: `gateway/providers/__init__.py` - Add restart logic to ProviderManager
- MODIFIED: `gateway/main.py` - Add health check endpoint, graceful shutdown
- MODIFIED: `gateway/server.py` - Rate limiting middleware
- NEW: `gateway/monitoring.py` - Health check logic
- NEW: `tests/gateway/test_load.py` - Load testing scenarios
- MODIFIED: `config/logging.py` - Add provider context to logs

**Technical Notes:**
- Use aiotools for graceful shutdown coordination
- Provider restarts use exponential backoff (1s, 2s, 4s, 8s, max 60s)
- Rate limiting: token bucket per (user_id, channel_id)
- Health checks: gateway alive + each provider connection status
- Load test: Locust or custom asyncio script

---

## Progress Tracking

| Phase | Status | Started | Completed | Notes |
|-------|--------|---------|-----------|-------|
| 1 - Provider Foundation | Pending | — | — | Provider abstraction + Discord wrapper |
| 2 - Gateway Integration & Email | Pending | — | — | Full pipeline + EmailProvider |
| 3 - CLI Client & Retirement | Planned | — | — | 3 plans in 2 waves |
| 4 - Production Hardening | Pending | — | — | Monitoring + load validation |

**Overall Progress:** 0/4 phases complete (0%)

---

## Out of Scope

**Explicitly deferred to future milestones:**

- **Slack Provider Implementation:** Architecture supports it, but actual Slack integration is separate work
- **Telegram Provider Implementation:** Same, architecture ready but implementation deferred
- **Web UI Client:** Gateway supports WebSocket clients, but building UI is separate milestone
- **Changes to mem0 Storage:** Databases remain untouched, no schema changes
- **Active-Mode Batching:** Complex optimization for 100+ user channels, defer to Phase 5+
- **Event Hooks System:** Already exists in gateway, no changes needed for MVP
- **Task Scheduler Enhancements:** Current scheduler sufficient, defer APScheduler migration
- **OpenTelemetry Tracing:** Basic structured logging sufficient for MVP
- **Circuit Breaker Patterns:** Add when scaling issues appear in production
- **Proactive Messages (ORS):** Requires separate planning phase

---

## Dependencies Between Phases

```
Phase 1 (Provider Foundation)
    ↓ Required for Phase 2
Phase 2 (Gateway Integration & Email)
    ↓ Required for Phase 3
Phase 3 (CLI Client & Retirement)
    ↓ Required for Phase 4
Phase 4 (Production Hardening)
```

**Critical Path:** Linear dependency chain, must complete phases sequentially.

**Estimated Timeline:**
- Phase 1: 1 week (Provider abstraction + Discord wrapper)
- Phase 2: 1 week (Gateway integration + EmailProvider)
- Phase 3: 1 week (CLI client + deletion)
- Phase 4: 1 week (Hardening + validation)

**Total:** 4 weeks for complete consolidation

---

## Risk Mitigation

**From research analysis (PITFALLS.md):**

| Risk | Severity | Mitigation | Phase |
|------|----------|------------|-------|
| Lost Stateful Features | CRITICAL | Strangler Fig pattern, behavioral tests | Phase 1-2 |
| Protocol Breaking Changes | CRITICAL | Version field from day one | Phase 1 |
| Incomplete Retirement | CRITICAL | Explicit deletion phase with criteria | Phase 3 |
| Gateway Bottleneck | CRITICAL | Stateless design, load testing | Phase 2, 4 |
| Silent Regression | HIGH | 20+ behavioral tests before extraction | Phase 2 |
| Monitoring Blindness | MEDIUM | Structured logging + health checks | Phase 4 |
| Provider Isolation Failure | MEDIUM | Separate process spaces, restart logic | Phase 4 |

**Success Indicators:**
- All behavioral tests pass after each phase
- mem0 databases untouched and functional
- Discord bot feature parity maintained
- Single entry point (`python -m gateway`)
- Clean deletion of discord_bot.py
- Load test validates 100+ user capacity

---

## Technical Decisions

| Decision | Rationale | Status |
|----------|-----------|--------|
| Providers run inside gateway process | Lower latency, simpler deployment | Decided |
| Strangler Fig pattern for Discord | Reduces risk, enables incremental migration | Decided |
| Delete discord_bot.py completely | Clean break over indefinite dual-write | Decided |
| Protocol versioning from Phase 1 | Prevents future breaking changes | Decided |
| Behavioral test suite before extraction | Catches lost features early | Decided |
| CLI as WebSocket client | Consistent interface for remote/local | Decided |
| Load testing in Phase 4 | Validates assumptions before production | Decided |

---

*Roadmap created: 2026-01-27*
*Phase 3 planned: 2026-01-27*
*Next step: Complete Phases 1-2 before executing Phase 3*
