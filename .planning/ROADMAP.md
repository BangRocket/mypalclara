# Gateway Consolidation Roadmap

**Project:** MyPalClara Gateway Architecture Consolidation
**Milestone:** Gateway Unification v1
**Created:** 2026-01-27
**Status:** Complete (All 6 phases)

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

**Plans:** 3 plans

Plans:
- [x] 01-01-PLAN.md — Core infrastructure: Provider ABC, ProviderManager, protocol versioning
- [x] 01-02-PLAN.md — DiscordProvider wrapping ClaraDiscordBot (Strangler Fig)
- [x] 01-03-PLAN.md — Gateway integration: wire ProviderManager into startup

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
- [x] Provider base class defines clear interface (start, stop, normalize_message, send_response)
- [x] DiscordProvider wraps discord_bot.py code without rewriting core logic
- [x] Gateway can start/stop DiscordProvider programmatically
- [x] Discord messages flow through Provider.normalize_message() to PlatformMessage
- [x] Protocol version field present in all gateway messages
- [x] No behavioral regression: Discord bot responds identically to before

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

**Plans:** 3 plans

Plans:
- [x] 02-01-PLAN.md — Integrate DiscordGatewayClient with MessageProcessor pipeline
- [x] 02-02-PLAN.md — Extract EmailProvider from email_monitor.py with event-based alerting
- [x] 02-03-PLAN.md — Create 20+ behavioral tests for Discord parity validation

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
- [x] Discord message -> Gateway processor -> LLM -> Response flows end-to-end
- [x] DiscordProvider receives response callbacks and streams to Discord channels
- [x] Tier-based model selection works (!high, !mid, !low prefixes)
- [x] Image/vision support functional through DiscordProvider
- [x] EmailProvider polls accounts and sends alerts via Discord provider
- [x] All 20+ behavioral tests pass (message dedup, queue batching, emotional context)
- [x] mem0 databases untouched and functional

**Key Risks Mitigated:**
- Gateway Bottleneck: Stateless design with session state in PostgreSQL
- Silent Regression: Behavioral test suite catches lost features
- Monitoring Blindness: Structured logging + alerts implemented

**Files Changed:**
- MODIFIED: `adapters/discord/gateway_client.py` - Wire response callbacks, add tier extraction
- NEW: `adapters/email/__init__.py` - Email adapter module exports
- NEW: `adapters/email/provider.py` - EmailProvider wrapping email_monitor.py
- NEW: `adapters/email/monitor.py` - Extracted EmailMonitor with async wrappers
- MODIFIED: `adapters/discord/main.py` - Discord adapter startup with gateway connection
- NEW: `tests/adapters/test_discord_gateway.py` - Integration tests
- NEW: `tests/adapters/test_email_provider.py` - EmailProvider unit tests
- NEW: `tests/adapters/test_discord_behavioral.py` - 20+ behavioral parity tests

**Technical Notes:**
- DiscordGatewayClient already implements response callbacks - need wiring fixes
- EmailProvider uses gateway event system to trigger Discord alerts
- ThreadPoolExecutor for blocking I/O (email IMAP)
- Behavioral tests document expected behaviors for regression detection

---

### Phase 3: CLI Client & Retirement

**Goal:** Build WebSocket CLI client, delete discord_bot.py and email_monitor.py completely, establish single entry point.

**Dependencies:** Phase 2 (requires working providers)

**Plans:** 5 plans (3 original + 2 gap closure)

Plans:
- [x] 03-01-PLAN.md — Refactor cli_bot.py to migration wrapper, add clara-cli script
- [x] 03-02-PLAN.md — Verify Phase 2 providers exist and deletion is safe (BLOCKERS FOUND)
- [x] 03-03-PLAN.md — Delete legacy files, update Docker Compose and documentation (PARTIAL)
- [x] 03-04-PLAN.md — Migrate email_monitor imports to adapters.email (GAP CLOSURE)
- [x] 03-05-PLAN.md — Integrate EmailProvider into gateway, delete email_monitor.py (GAP CLOSURE)

**Requirements Coverage:**
- CLI client connects to gateway via WebSocket
- `python -m gateway` is the only entry point needed
- ~~`discord_bot.py` deleted (code merged into gateway)~~ REVISED: Keep wrapped by DiscordProvider
- `email_monitor.py` deleted (imports migrated to adapters.email)

**Deliverables:**
1. CLI client refactored to connect via WebSocket (not direct MemoryManager)
2. `cli_bot.py` entry point calls gateway CLI client
3. ~~`discord_bot.py` deleted~~ REVISED: Remains wrapped by DiscordProvider (strangler fig)
4. `email_monitor.py` deleted (all code moved to adapters/email/)
5. `poetry run python -m gateway` starts Discord and Email providers
6. Documentation updated (CLAUDE.md, README.md)
7. Docker Compose updated to single gateway service

**Success Criteria:**
- [x] CLI client connects to gateway WebSocket server
- [x] CLI messages flow through gateway processor with full tool support
- [x] DiscordProvider wraps discord_bot.py (strangler fig pattern - permanent)
- [x] `email_monitor.py` deleted from repository
- [x] `python -m gateway --enable-email` starts EmailProvider
- [x] No import errors or broken references after deletion
- [x] docker-compose.yml runs single gateway container
- [x] All integration tests pass (71 tests)

**Key Risks Mitigated:**
- Incomplete Code Retirement: Explicit deletion phase with completion criteria
- Feature Flag Sprawl: No feature flags needed, clean break

**Files Changed:**
- MODIFIED: `cli_bot.py` - Use WebSocket client instead of direct calls
- NEW: `gateway/providers/cli.py` - CLI provider for local terminal
- RETAINED: `discord_bot.py` - Wrapped by DiscordProvider (strangler fig pattern)
- DELETED: `email_monitor.py` - Logic moved to adapters/email/
- MODIFIED: `gateway/main.py` - Start Discord and Email providers
- MODIFIED: `docker-compose.yml` - Single gateway service
- MODIFIED: `CLAUDE.md` - Update deployment instructions
- MODIFIED: `README.md` - Update architecture documentation

**Technical Notes:**
- CLI provider runs in-process (no WebSocket for local mode)
- CLI WebSocket client used only when connecting to remote gateway
- Gateway determines local vs remote CLI based on connection source
- Auto-migration runs on gateway startup (same as before)
- discord_bot.py RETAINED: Strangler fig pattern is intentional architecture

---

### Phase 4: Production Hardening

**Goal:** Add monitoring, error recovery, and load validation to ensure production readiness.

**Dependencies:** Phase 3 (requires complete system)

**Plans:** 3 plans

Plans:
- [x] 04-01-PLAN.md — Add dependencies (tenacity, structlog), implement rate limiting and structured logging
- [x] 04-02-PLAN.md — Health check endpoints, graceful shutdown, provider restart with backoff
- [x] 04-03-PLAN.md — Load testing validation, resource limits, documentation updates

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
- [x] Provider crash triggers auto-restart (not gateway crash)
- [x] Rate limits prevent spam (configurable per provider)
- [x] `/health` endpoint reports gateway + provider status
- [x] Logs include provider_name, user_id, channel_id context
- [x] Gateway handles 100+ concurrent users without degradation
- [x] Graceful shutdown completes pending responses before exit
- [x] Memory usage stable under sustained load
- [x] All existing features functional (Discord streaming, MCP tools, sandbox, image vision, email alerts)

**Key Risks Mitigated:**
- Gateway Bottleneck: Load testing validates assumptions
- Monitoring Blindness: Health checks and structured logging
- Single Point of Failure: Provider isolation prevents cascading failures

**Files Changed:**
- MODIFIED: `gateway/providers/__init__.py` - Add restart logic to ProviderManager
- MODIFIED: `gateway/main.py` - Add health check endpoint, graceful shutdown
- MODIFIED: `gateway/server.py` - Rate limiting middleware
- NEW: `gateway/health.py` - Health check endpoints
- NEW: `gateway/rate_limiter.py` - Token bucket rate limiting
- NEW: `tests/gateway/test_load.py` - Load testing scenarios
- MODIFIED: `config/logging.py` - Add structlog integration
- MODIFIED: `CLAUDE.md` - Production configuration documentation

**Technical Notes:**
- Use tenacity for provider restart with exponential backoff (1s, 2s, 4s, 8s, max 60s)
- Rate limiting: token bucket per (user_id, channel_id)
- Health checks: /health (liveness), /ready (readiness), /status (detailed)
- Structured logging via structlog with JSON output in production
- Load test: custom asyncio script (100 clients, 60 seconds)

---

### Phase 5: Email Provider Polish

**Goal:** Fix EmailProvider type safety and wire email alert consumer for functional email→Discord notifications.

**Dependencies:** Phase 4 (requires complete system)

**Gap Closure:** Closes gaps from v1-MILESTONE-AUDIT.md

**Plans:** 2 plans

Plans:
- [x] 05-01-PLAN.md — EmailProvider inherits Provider ABC for type safety
- [x] 05-02-PLAN.md — Register email alert consumer to send Discord notifications

**Requirements Coverage:**
- Integration gap: EmailProvider type safety
- Flow gap: Email Alert Flow consumer registration

**Deliverables:**
1. EmailProvider inherits from Provider ABC
2. Type annotations for EmailProvider methods
3. Email alert event consumer registered in gateway
4. Discord notifications sent when important emails arrive

**Success Criteria:**
- [x] EmailProvider passes mypy type checking
- [x] EmailProvider listed in ProviderManager type hints
- [x] Email alerts trigger Discord messages via consumer
- [x] Integration test validates email→Discord flow

**Files Changed:**
- MODIFIED: `adapters/email/provider.py` - Inherit Provider ABC, add type hints
- MODIFIED: `gateway/providers/__init__.py` - Update type hints for EmailProvider
- MODIFIED: `gateway/main.py` - Register email alert consumer
- NEW: `tests/adapters/test_email_alert_flow.py` - E2E email→Discord test

**Technical Notes:**
- EmailProvider must implement: start(), stop(), normalize_message(), send_response()
- Consumer listens for MESSAGE_RECEIVED events with source="email"
- Alert routing uses DiscordProvider.send_response() for notifications

---

### Phase 6: Library Updates

**Goal:** Update websockets library to remove deprecation warnings.

**Dependencies:** Phase 4 (requires complete system)

**Gap Closure:** Closes tech debt from v1-MILESTONE-AUDIT.md

**Plans:** 1 plan

Plans:
- [x] 06-01-PLAN.md — Update websockets API to modern syntax

**Requirements Coverage:**
- Tech debt: websockets.server.serve deprecation
- Tech debt: websockets.client.WebSocketClientProtocol deprecation

**Deliverables:**
1. Gateway server uses modern websockets API
2. CLI client uses modern websockets API
3. No deprecation warnings on startup

**Success Criteria:**
- [x] Gateway starts without deprecation warnings
- [x] CLI client connects without deprecation warnings
- [x] All existing WebSocket tests pass
- [x] Load test still passes with updated library

**Files Changed:**
- MODIFIED: `gateway/server.py` - Update serve() call to modern API
- MODIFIED: `adapters/cli/gateway_client.py` - Update client connection
- MODIFIED: `pyproject.toml` - Pin websockets version if needed

**Technical Notes:**
- Check websockets changelog for migration guide
- May require websockets>=12.0 for new API
- Test backward compatibility with existing adapters

---

## Progress Tracking

| Phase | Status | Started | Completed | Notes |
|-------|--------|---------|-----------|-------|
| 1 - Provider Foundation | Complete | 2026-01-28 | 2026-01-28 | 3 plans, 13 min total |
| 2 - Gateway Integration & Email | Complete | 2026-01-28 | 2026-01-28 | 3 plans, 13 min total |
| 3 - CLI Client & Retirement | Complete | 2026-01-28 | 2026-01-28 | 5 plans, 12 min total (inc. gap closure) |
| 4 - Production Hardening | Complete | 2026-01-28 | 2026-01-28 | 3 plans, ~23 min total (inc. checkpoint) |
| 5 - Email Provider Polish | Complete | 2026-01-28 | 2026-01-28 | 2 plans, ~4 min total |
| 6 - Library Updates | Complete | 2026-01-28 | 2026-01-28 | 1 plan, ~3 min total |

**Overall Progress:** 6/6 phases complete (100%)

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
- **DiscordProvider Standalone Refactor:** Strangler fig pattern is permanent architecture

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
    ↓ Required for Phase 5-6
Phase 5 (Email Provider Polish) ←─┐
                                  ├─ Can run in parallel
Phase 6 (Library Updates) ←───────┘
```

**Critical Path:** Phases 1-4 are sequential. Phases 5-6 can run in parallel after Phase 4.

**Estimated Timeline:**
- Phase 1: 1 week (Provider abstraction + Discord wrapper) — COMPLETE
- Phase 2: 1 week (Gateway integration + EmailProvider) — COMPLETE
- Phase 3: 1 week (CLI client + deletion) — COMPLETE
- Phase 4: 1 week (Hardening + validation) — COMPLETE
- Phase 5: 1 day (Email provider type safety + alert consumer) — Gap closure
- Phase 6: 1 day (websockets library update) — Gap closure

**Total:** 4 weeks + 2 days for complete consolidation with gap closure

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
- ~~Clean deletion of discord_bot.py~~ REVISED: Wrapped by DiscordProvider
- Clean deletion of email_monitor.py
- Load test validates 100+ user capacity

---

## Technical Decisions

| Decision | Rationale | Status |
|----------|-----------|--------|
| Providers run inside gateway process | Lower latency, simpler deployment | Decided |
| Strangler Fig pattern for Discord | Reduces risk, enables incremental migration | Decided |
| ~~Delete discord_bot.py completely~~ | ~~Clean break over indefinite dual-write~~ | **Revised** - Keep wrapped permanently |
| Delete email_monitor.py | Imports migrated to adapters.email | Decided |
| Protocol versioning from Phase 1 | Prevents future breaking changes | Decided |
| Behavioral test suite before extraction | Catches lost features early | Decided |
| CLI as WebSocket client | Consistent interface for remote/local | Decided |
| Load testing in Phase 4 | Validates assumptions before production | Decided |
| Keep discord_bot.py wrapped | DiscordProvider strangler fig is permanent architecture | **New** - Phase 3 |

---

*Roadmap created: 2026-01-27*
*Phase 1 planned: 2026-01-27*
*Phase 2 planned: 2026-01-27*
*Phase 3 planned: 2026-01-27*
*Phase 3 gap closure: 2026-01-28*
*Phase 4 planned: 2026-01-27*
*Phase 5-6 gap closure: 2026-01-28*
*Phase 5-6 complete: 2026-01-28*
*Milestone complete: 2026-01-28*
