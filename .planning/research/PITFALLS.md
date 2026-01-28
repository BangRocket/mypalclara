# Domain Pitfalls: Gateway Consolidation (Monolith → Provider Architecture)

**Domain:** Migrating 3700-line Discord bot into gateway/provider architecture
**Researched:** 2026-01-27
**Context:** Strangler Fig pattern migration from discord_bot.py to gateway/providers/discord.py

## Critical Pitfalls

These mistakes cause rewrites, data loss, or catastrophic regressions.

### Pitfall 1: Incomplete Code Retirement (The Zombie Monolith)

**What goes wrong:** Teams extract new services but never retire the old code path. Both systems run in parallel indefinitely, creating dual-write problems, divergent behavior, and maintenance nightmares. The migration is declared "complete" while the monolith continues handling production traffic.

**Why it happens:** Short-term focus and competing priorities. Deleting the old code requires comprehensive testing and coordinated deployment. Teams lose momentum after the "interesting" extraction work is done.

**Consequences:**
- Dual-write bugs (state divergence between old and new paths)
- Memory leaks from running both systems
- Silent feature drift as only one path gets updates
- Impossible to debug ("which code handled this request?")

**Detection:**
- Feature flag for new path remains at <100% for >2 sprint cycles
- Both `discord_bot.py` and `gateway/providers/discord.py` receiving commits
- Monitoring shows traffic split between both paths
- Team debates "which implementation is canonical"

**Prevention:**
- Set explicit retirement timeline BEFORE starting extraction (Phase N: retire by date X)
- Create "deletion checklist" as part of migration plan
- Measure % traffic on new path; auto-rollback if <95% after 2 weeks
- Make deletion a separate tracked phase with completion criteria

**Phase mapping:** Phase 4 (Validation & Retirement) must exist as first-class phase, not assumed cleanup.

---

### Pitfall 2: Lost Stateful Features (The Silent Regression)

**What goes wrong:** Complex stateful features like message caching, queue batching, or emotional context tracking get simplified or dropped during consolidation. The gateway implements a "cleaner" version that lacks critical state management, causing subtle but pervasive behavioral regressions.

**Why it happens:** The provider abstraction forces stateless thinking. Features that were implicit in the monolith (e.g., Discord's message cache, queue position tracking, sentiment continuity) don't have obvious homes in the new architecture. Teams rationalize: "That complexity wasn't essential."

**Consequences:**
- Message deduplication breaks → duplicate processing
- Queue batching lost → floods chat with individual responses
- Emotional context lost → tone-deaf responses after 30min gaps
- Auto-continue heuristics lost → users must manually confirm every step

**Detection:**
- User complaints about "Clara feels different" or "less smart"
- Logs show duplicate message IDs being processed
- Active mode channels receive 5 individual responses instead of 1 batched reply
- Sentiment analysis shows flat affect (no emotional memory)
- Increased "Do you want me to proceed?" spam

**Prevention:**
- **Feature inventory audit:** List EVERY stateful feature in the monolith before extraction
  - Message dedup TTL cache (60s window)
  - Queue batching for active mode (consecutive non-mention messages)
  - Emotional context finalization (30min gap detection)
  - Auto-continue pattern matching (permission-seeking questions)
  - Tier classification caching (per conversation)
  - Image batch processing state (multi-image conversations)
- **State mapping document:** For each feature, specify where state lives in new architecture
  - Gateway-level: Cross-adapter state (global rate limits)
  - Provider-level: Platform-specific state (Discord message cache, queue)
  - Session-level: Conversation state (emotional context, tier)
- **Behavioral test suite:** Before extraction, capture monolith behavior as tests
  - Test: Same message sent twice within 60s → only processes once
  - Test: 3 active-mode messages queued → 1 batched response
  - Test: 30min gap → emotional context finalized to mem0
- **Canary deployments:** Run both systems in parallel, compare outputs

**Phase mapping:**
- Phase 1 (Pre-extraction): Feature inventory + state mapping
- Phase 2 (During extraction): State management implementation
- Phase 3 (Validation): Behavioral parity testing

---

### Pitfall 3: Protocol Versioning Naivety (The Breaking Change Spiral)

**What goes wrong:** The gateway protocol (WebSocket message types) evolves without versioning. Adding fields to `MessageRequest` or changing enum values breaks existing adapters. The team hard-codes protocol assumptions ("adapters will always send X") that become technical debt.

**Why it happens:** Initial protocol seems simple and stable. Versioning feels like premature abstraction. The gateway and first adapter are developed in lockstep, masking compatibility issues.

**Consequences:**
- Adapter disconnects when gateway updates
- Silent data loss (new fields ignored by old adapters)
- Can't deploy gateway and adapters independently
- Future adapters inherit broken assumptions

**Detection:**
- Adapter crashes with "unknown field" errors after gateway deployment
- Gateway logs show adapters reconnecting repeatedly
- Rollback required to restore adapter connectivity
- Adding new adapter requires gateway changes

**Prevention:**
- **Protocol versioning from day 1:**
  - Every protocol message includes `"protocol_version": "1.0"`
  - Gateway supports N and N-1 versions simultaneously
  - Registration handshake negotiates version
- **Backward compatibility rules:**
  - Adding optional fields: OK
  - Removing fields: Requires major version bump + 6-month deprecation
  - Changing field semantics: New field + deprecation of old
- **Protocol schema validation:**
  - Use Pydantic models for all messages (already present in `protocol.py`)
  - Automated tests for forward/backward compatibility
  - CI fails if protocol breaks without version bump
- **Adapter SDK:**
  - Provide typed client library for adapters
  - SDK abstracts protocol details and handles versioning
  - Breaking changes detected at compile time (TypeScript) or import time (Python)

**Phase mapping:**
- Phase 1 (Gateway Core): Protocol versioning infrastructure
- Phase 2 (First Adapter): Version negotiation handshake
- Phase 3+ (Additional Adapters): Leverage existing version support

---

### Pitfall 4: Façade Performance Bottleneck (The Gateway Choke Point)

**What goes wrong:** The gateway becomes a single point of failure and performance bottleneck. All requests funnel through one process, creating latency, throughput limits, and cascading failures when the gateway crashes.

**Why it happens:** Initial architecture prioritizes simplicity (one gateway, many adapters). Under load, the gateway's CPU/memory/network becomes saturated. Async I/O mitigates but doesn't eliminate the bottleneck.

**Consequences:**
- Gateway crashes take down ALL platforms simultaneously
- Discord, CLI, Slack all offline when gateway restarts
- Latency increases under load (queued requests)
- Can't scale horizontally (gateway is stateful singleton)

**Detection:**
- Gateway CPU/memory usage >80% during normal load
- Request latency P95 >2s (should be <500ms)
- Adapter reconnect storms after gateway restart
- Throughput plateau despite adding more adapters

**Prevention:**
- **Stateless gateway design:**
  - Session state in external store (Redis, PostgreSQL)
  - No in-memory caches that can't be rebuilt
  - Enable horizontal scaling with load balancer
- **Circuit breakers:**
  - Gateway rejects requests when CPU >90% (fail fast)
  - Adapters retry with exponential backoff
  - Health checks separate from request path
- **Resource limits:**
  - Max concurrent requests per adapter (backpressure)
  - Request timeout enforced (no infinite hangs)
  - Memory limits per LLM call (prevent OOM)
- **Monitoring:**
  - Track gateway throughput (requests/sec)
  - Track P50/P95/P99 latency
  - Alert if latency >1s or throughput drops >50%

**Phase mapping:**
- Phase 2 (Gateway Core): Stateless design + resource limits
- Phase 3 (Production Hardening): Circuit breakers + monitoring
- Phase 4+ (Scale): Horizontal scaling + load balancer

---

### Pitfall 5: Feature Flag Sprawl (The Configuration Maze)

**What goes wrong:** Feature flags multiply rapidly during migration. `USE_DISCORD_ADAPTER`, `ENABLE_QUEUE_BATCHING`, `GATEWAY_EMOTIONAL_CONTEXT`, etc. Each flag creates 2^N code paths. The system becomes impossible to test comprehensively. Flags remain in code for months after migration "completes."

**Why it happens:** Feature flags are cheap to create and useful for incremental rollout. Teams add flags liberally but never remove them. The carrying cost isn't visible until the codebase is riddled with conditionals.

**Consequences:**
- Knight Capital-style incidents ($460M loss from forgotten flags)
- Impossible to reason about code ("which path actually runs?")
- Test combinatorial explosion (can't test all flag states)
- Production incidents from flag misconfigurations
- Long-lived flags become permanent technical debt

**Detection:**
- >5 feature flags active simultaneously
- Flags older than 3 months still in code
- Code has nested if/else blocks >3 levels deep for flags
- Team debates "what does this flag actually control?"
- Production config differs from staging (drift)

**Prevention:**
- **Flag lifecycle policy:**
  - Every flag has expiration date (30/60/90 days)
  - Automated alerts 2 weeks before expiration
  - CI fails if flag older than expiration without explicit extension
  - Flag removal is a tracked task (not assumed cleanup)
- **Flag hierarchy:**
  - ONE master toggle: `USE_DISCORD_ADAPTER` (enable/disable entire provider)
  - No sub-feature flags (all-or-nothing per adapter)
  - If sub-features needed, create separate provider variant
- **Testing strategy:**
  - Test only: old path (100% off) and new path (100% on)
  - No testing of mixed states (flag=50%)
  - Canary rollout: 1% → 10% → 50% → 100%, not prolonged 50/50
- **Flag audit:**
  - Monthly review of all active flags
  - Mandatory removal or justification for extension

**Phase mapping:**
- Phase 0 (Planning): Define flag lifecycle policy
- Phase 2 (Extraction): Create master toggle, set expiration
- Phase 4 (Retirement): Delete flag + old code path

---

## Moderate Pitfalls

Mistakes that cause delays, technical debt, or reduced quality.

### Pitfall 6: Adapter State Isolation Failure

**What goes wrong:** Multiple adapter instances (e.g., Discord bot sharding) share state incorrectly, causing race conditions, duplicate processing, or lost messages.

**Prevention:**
- Use database-level concurrency controls (row locks, transactions)
- Include adapter instance ID in all state keys
- Idempotent message processing (deduplication by message ID)
- Test with multiple adapter instances running concurrently

**Phase mapping:** Phase 2 (Provider Implementation) - concurrent instance testing required.

---

### Pitfall 7: Tool Execution Context Lost

**What goes wrong:** Tool calls in the monolith have rich context (user, channel, platform). The gateway abstracts this away, breaking tools that depend on Discord-specific features (e.g., `create_file_attachment` sends to Discord channel).

**Prevention:**
- Tool context includes platform type + capabilities dict
- Provider-specific tools registered dynamically (not hardcoded in gateway)
- Gateway passes `ToolContext` with platform, user, channel metadata
- Tools check capabilities before execution (`ctx.has_capability("discord_files")`)

**Phase mapping:** Phase 2 (Tool Integration) - context preservation is critical.

---

### Pitfall 8: Monitoring Blindness During Migration

**What goes wrong:** Old monitoring (Discord bot logs, health checks) doesn't cover the gateway. Silent failures in gateway → adapter communication go undetected. Team discovers issues only via user reports.

**Prevention:**
- Gateway metrics: request rate, latency, error rate, active connections
- Adapter metrics: reconnect count, message send/receive rate, queue depth
- End-to-end health checks (send test message, verify response)
- Alerts for: gateway crash, adapter disconnect >60s, latency >2s
- Dashboards comparing old vs new path metrics during migration

**Phase mapping:** Phase 1 (Gateway Core) - monitoring is infrastructure, not afterthought.

---

### Pitfall 9: Synchronous Tool Calls in Async Gateway

**What goes wrong:** Tool executor calls blocking functions (LLM, mem0, database) without proper executor isolation. Gateway event loop blocks, starving other adapters.

**Prevention:**
- All blocking I/O wrapped in `loop.run_in_executor(BLOCKING_IO_EXECUTOR, ...)`
- Dedicated thread pool for blocking operations (20+ threads)
- Never `time.sleep()` or blocking HTTP calls on event loop
- Use async libraries where available (aiohttp, asyncpg)

**Phase mapping:** Phase 2 (Tool Executor) - async/sync boundary is subtle, test under load.

---

### Pitfall 10: Session Timeout Handling Mismatch

**What goes wrong:** The monolith handles 30-minute gaps by finalizing emotional context and extracting topics. The gateway doesn't detect gaps correctly, losing conversational continuity.

**Prevention:**
- Gateway tracks last message timestamp per session (in session store)
- On new message, calculate gap: `now - last_message_time`
- If gap >30min, trigger finalization before processing new message
- Ensure finalization logic preserved exactly as monolith
- Test: Send message, wait 31min, send another → verify finalization ran

**Phase mapping:** Phase 2 (Message Processor) - session lifecycle logic must be preserved.

---

## Minor Pitfalls

Mistakes that cause annoyance but are fixable.

### Pitfall 11: Image Batching Lost in Abstraction

**What goes wrong:** The monolith batches >1 image into sequential LLM calls to avoid 413 payload errors. The gateway implements simpler single-image handling, breaking multi-image messages.

**Prevention:**
- Preserve `MAX_IMAGES_PER_REQUEST` batching logic in gateway
- Test with 5-image message, verify batched processing
- Gateway protocol supports image arrays, not just single image

**Phase mapping:** Phase 2 (Vision Support) - test with multi-image scenarios.

---

### Pitfall 12: Auto-Continue Pattern Matching Simplified

**What goes wrong:** The monolith has 20+ patterns for detecting permission-seeking questions ("want me to do it?", "shall I proceed?"). The gateway uses a simpler regex, missing edge cases.

**Prevention:**
- Port exact pattern list from monolith (`AUTO_CONTINUE_PATTERNS`)
- Test each pattern individually
- Metrics: track auto-continue trigger rate (should match monolith baseline)

**Phase mapping:** Phase 2 (Response Generation) - preserve UX heuristics exactly.

---

### Pitfall 13: Tier Classification Caching Missing

**What goes wrong:** The monolith caches tier classification (high/mid/low) per conversation to avoid re-classifying on every message. The gateway re-classifies every time, wasting fast model calls.

**Prevention:**
- Cache tier decision in session metadata
- Invalidate cache after 10 messages or 30min gap
- Metrics: track classification rate (should be <10% of messages)

**Phase mapping:** Phase 3 (Optimization) - caching is not MVP but prevents waste.

---

### Pitfall 14: Stop Phrase Queue Cancellation Broken

**What goes wrong:** The monolith cancels running asyncio tasks when user sends stop phrase ("clara stop"). The gateway doesn't propagate cancellation to adapters, leaving tasks running.

**Prevention:**
- Gateway protocol includes `CancelMessage` type (already in `protocol.py`)
- Adapter sends cancel, gateway propagates to LLM orchestrator
- LLM orchestrator cancels asyncio task, sends `CancelledMessage` back
- Test: Start long task, send stop phrase, verify task cancelled <1s

**Phase mapping:** Phase 2 (Control Flow) - stop phrases are core UX.

---

### Pitfall 15: Discord Markdown Formatting Lost

**What goes wrong:** The monolith includes Discord-specific formatting hints in system prompt ("Use Discord markdown", "Use `create_file_attachment` for large content"). The gateway uses generic prompts, producing less optimal Discord responses.

**Prevention:**
- Gateway supports platform-specific system prompts
- Provider injects Discord guidelines during context building
- System prompt includes platform field: `"platform": "discord"`
- Clara's prompt builder switches on platform type

**Phase mapping:** Phase 2 (Prompt Building) - preserve platform-specific guidance.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Phase 1: Gateway Core | Protocol versioning naivety (#3) | Add protocol version field, handshake negotiation |
| Phase 1: Gateway Core | Façade bottleneck (#4) | Design stateless from start, use external session store |
| Phase 2: Provider Extraction | Lost stateful features (#2) | Feature inventory audit before extraction |
| Phase 2: Provider Extraction | Tool context lost (#7) | Preserve ToolContext with platform metadata |
| Phase 2: Provider Extraction | Session timeout mismatch (#10) | Port exact 30min gap detection logic |
| Phase 3: Queue Integration | Adapter state isolation (#6) | Test with concurrent adapter instances |
| Phase 3: Queue Integration | Batching lost (#11) | Preserve image batching, active-mode message batching |
| Phase 4: Validation | Incomplete retirement (#1) | Set deletion deadline BEFORE extraction starts |
| Phase 4: Validation | Monitoring blindness (#8) | Deploy metrics/alerts in Phase 1, not Phase 4 |
| Phase 5: Feature Flags | Flag sprawl (#5) | ONE master toggle, 90-day expiration policy |

---

## Consolidation-Specific Anti-Patterns

These are specific to provider architecture migrations, not general microservices splits.

### Anti-Pattern 1: Provider = Dumb Pipe

**What it is:** Treating the provider as a pure protocol translator with zero logic. All intelligence moves to the gateway, making the provider a thin shim.

**Why it's wrong:** Platform-specific features (Discord queue batching, message caching, typing indicators) don't fit in the gateway. Pushing them down creates leaky abstractions and violates separation of concerns.

**Correct approach:** Provider owns platform-specific state and behavior. Gateway owns cross-platform logic (memory, LLM, tools). Clear boundary: "Would another platform need this? No → provider. Yes → gateway."

---

### Anti-Pattern 2: Gateway = Orchestrator God Object

**What it is:** The gateway handles message routing, context building, LLM calls, tool execution, response streaming, session management, and adapter lifecycle. It becomes a 5000-line god object.

**Why it's wrong:** Violates single responsibility. Hard to test, reason about, or scale. Future features have no clear home.

**Correct approach:** Gateway delegates to specialized components:
- `MessageProcessor` - context building, LLM orchestration
- `ToolExecutor` - tool dispatch, result handling
- `LLMOrchestrator` - streaming, tool detection
- `SessionManager` - session lifecycle, timeout detection
- Gateway only routes messages between these components

---

### Anti-Pattern 3: Premature Abstraction

**What it is:** Designing the gateway to support "any platform" before the second adapter exists. Over-engineering the protocol to handle hypothetical features.

**Why it's wrong:** Wastes time on unused abstractions. The second adapter reveals different constraints than imagined. YAGNI violation.

**Correct approach:** Design for Discord (the only adapter). Add abstractions when the second adapter (CLI, Slack) reveals actual commonalities. Strangler Fig is incremental, not big design up front.

---

## Sources

- [Microservices vs Monoliths in 2026: When Each Architecture Wins](https://www.javacodegeeks.com/2025/12/microservices-vs-monoliths-in-2026-when-each-architecture-wins.html)
- [How to break a Monolith into Microservices](https://martinfowler.com/articles/break-monolith-into-microservices.html)
- [9 Most Common Mistakes when Migrating from Monolith to Microservices](https://nglogic.com/9-most-common-mistakes-when-migrating-from-monolith-to-microservices/)
- [Strangler Fig Pattern - AWS Prescriptive Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/strangler-fig.html)
- [Strangler Fig Pattern - Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/patterns/strangler-fig)
- [Best Practices for Migrating from a Homegrown Feature Management Solution](https://docs.getunleash.io/topics/feature-flag-migration/feature-flag-migration-best-practices)
- [Feature Toggles (aka Feature Flags)](https://martinfowler.com/articles/feature-toggles.html)
- [Data Versioning and Schema Evolution Patterns](https://bool.dev/blog/detail/data-versioning-patterns)
- [Adapter pattern](https://grokipedia.com/page/Adapter_pattern)
- [Discord Bots and State Management](https://medium.com/better-programming/discord-bots-and-state-management-22775c1f7aeb)
- [Cache customization | discord.js Guide](https://discordjs.guide/miscellaneous/cache-customization.html)
- [Stateful vs stateless applications](https://www.redhat.com/en/topics/cloud-native-apps/stateful-vs-stateless)
- [Converting stateful application to stateless using AWS services](https://aws.amazon.com/blogs/architecture/converting-stateful-application-to-stateless-using-aws-services/)
- [CWE-362: Concurrent Execution using Shared Resource with Improper Synchronization](https://cwe.mitre.org/data/definitions/362.html)
