# Requirements: Clara Gateway Consolidation

**Defined:** 2026-01-27
**Core Value:** Single daemon, multiple providers

## v1 Requirements

Requirements for Gateway Consolidation milestone. Each maps to roadmap phases.

### Gateway Architecture

- [ ] **GATE-01**: Gateway daemon runs all providers from single process
- [ ] **GATE-02**: Gateway supports provider lifecycle management (start, stop, restart)
- [ ] **GATE-03**: Gateway provides unified message routing to all providers
- [ ] **GATE-04**: Gateway includes protocol versioning for adapter compatibility
- [ ] **GATE-05**: Provider architecture supports adding Slack/Telegram later

### Discord Provider

- [ ] **DISC-01**: Discord provider integrated into gateway (not separate process)
- [ ] **DISC-02**: Discord bot responds to messages with streaming LLM responses
- [ ] **DISC-03**: Discord provider maintains message queuing and batching behavior
- [ ] **DISC-04**: Discord provider supports multi-model tier selection (!high, !mid, !low)
- [ ] **DISC-05**: Discord provider supports image/vision capabilities
- [ ] **DISC-06**: Discord provider maintains reply chain tracking
- [ ] **DISC-07**: discord_bot.py deleted completely after migration

### Email Provider

- [ ] **EMAL-01**: Email provider integrated into gateway
- [ ] **EMAL-02**: Email monitoring with rule-based alerts continues working
- [ ] **EMAL-03**: Email provider uses gateway event system for alerts
- [ ] **EMAL-04**: email_monitor.py deleted completely after migration

### CLI Client

- [ ] **CLI-01**: CLI client connects to gateway via WebSocket
- [ ] **CLI-02**: CLI messages flow through gateway processor with tool support
- [ ] **CLI-03**: CLI client supports both local and remote gateway connections

### Entry Point

- [ ] **ENTR-01**: `python -m gateway` is the only entry point needed
- [ ] **ENTR-02**: Gateway starts all providers (Discord, Email, CLI) from single command
- [ ] **ENTR-03**: Docker Compose runs single gateway service (not multiple)

### Data Preservation

- [ ] **DATA-01**: mem0 databases remain untouched and functional
- [ ] **DATA-02**: Session history and message storage continues working
- [ ] **DATA-03**: Project/user isolation maintained through consolidation

### Feature Parity

- [ ] **FEAT-01**: Memory system (mem0) provides context from past conversations
- [ ] **FEAT-02**: MCP plugins extend Clara with external tools
- [ ] **FEAT-03**: Code execution via Docker/Incus sandbox works
- [ ] **FEAT-04**: Hooks and scheduler trigger on events
- [ ] **FEAT-05**: Multi-model tier support continues working
- [ ] **FEAT-06**: All behavioral tests pass (message dedup, emotional context, etc.)

### Production Readiness

- [ ] **PROD-01**: Provider crash triggers auto-restart (not gateway crash)
- [ ] **PROD-02**: Rate limiting prevents spam (configurable per provider)
- [ ] **PROD-03**: Health check endpoint reports gateway and provider status
- [ ] **PROD-04**: Structured logging includes provider context
- [ ] **PROD-05**: Gateway handles 100+ concurrent users without degradation
- [ ] **PROD-06**: Graceful shutdown completes pending responses

## v2 Requirements

Deferred to future milestones. Tracked but not in current roadmap.

### Additional Providers

- **PROV-01**: Slack provider implementation
- **PROV-02**: Telegram provider implementation
- **PROV-03**: Web UI client with WebSocket connection

### Advanced Features

- **ADV-01**: Active-mode batching for high-activity channels
- **ADV-02**: OpenTelemetry tracing for distributed debugging
- **ADV-03**: Circuit breaker patterns for resilience
- **ADV-04**: Proactive messages and ORS (Operational Runtime System)

### Scaling

- **SCAL-01**: Multi-gateway distributed architecture
- **SCAL-02**: Redis-based session state for horizontal scaling
- **SCAL-03**: Load balancer for multiple gateway instances

## Out of Scope

Explicitly excluded from Gateway Consolidation milestone. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Changes to mem0 storage | Databases must remain untouched per constraints |
| Slack provider implementation | Architecture only, actual implementation deferred to v2 |
| Telegram provider implementation | Architecture only, actual implementation deferred to v2 |
| Web UI client | Gateway supports it, but building UI is separate work |
| Active-mode batching optimization | Complex feature for 100+ user channels, defer to v2 |
| APScheduler migration | Current scheduler sufficient, defer until scaling needs |
| OpenTelemetry tracing | Basic structured logging sufficient for MVP |
| Circuit breaker patterns | Add when scaling issues appear in production |
| Proactive messages (ORS) | Requires separate planning phase |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| GATE-01 | Phase 1 | Pending |
| GATE-02 | Phase 1 | Pending |
| GATE-03 | Phase 2 | Pending |
| GATE-04 | Phase 1 | Pending |
| GATE-05 | Phase 1 | Pending |
| DISC-01 | Phase 1 | Pending |
| DISC-02 | Phase 2 | Pending |
| DISC-03 | Phase 2 | Pending |
| DISC-04 | Phase 2 | Pending |
| DISC-05 | Phase 2 | Pending |
| DISC-06 | Phase 2 | Pending |
| DISC-07 | Phase 3 | Pending |
| EMAL-01 | Phase 2 | Pending |
| EMAL-02 | Phase 2 | Pending |
| EMAL-03 | Phase 2 | Pending |
| EMAL-04 | Phase 3 | Pending |
| CLI-01 | Phase 3 | Pending |
| CLI-02 | Phase 3 | Pending |
| CLI-03 | Phase 3 | Pending |
| ENTR-01 | Phase 3 | Pending |
| ENTR-02 | Phase 3 | Pending |
| ENTR-03 | Phase 3 | Pending |
| DATA-01 | Phase 2 | Pending |
| DATA-02 | Phase 2 | Pending |
| DATA-03 | Phase 2 | Pending |
| FEAT-01 | Phase 2 | Pending |
| FEAT-02 | Phase 2 | Pending |
| FEAT-03 | Phase 2 | Pending |
| FEAT-04 | Phase 2 | Pending |
| FEAT-05 | Phase 2 | Pending |
| FEAT-06 | Phase 2 | Pending |
| PROD-01 | Phase 4 | Pending |
| PROD-02 | Phase 4 | Pending |
| PROD-03 | Phase 4 | Pending |
| PROD-04 | Phase 4 | Pending |
| PROD-05 | Phase 4 | Pending |
| PROD-06 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 35 total
- Mapped to phases: 35
- Unmapped: 0 ✓

---
*Requirements defined: 2026-01-27*
*Last updated: 2026-01-27 after roadmap creation*
