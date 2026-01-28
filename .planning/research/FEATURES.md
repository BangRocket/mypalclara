# Feature Landscape: Multi-Provider Bot Gateway

**Domain:** Multi-platform messaging gateway with AI backend
**Researched:** 2026-01-27
**Overall confidence:** HIGH (based on production systems analysis)

## Executive Summary

Modern multi-provider bot gateways (2025-2026) have converged on a three-layer architecture: **Gateway daemon** (provider orchestration), **WebSocket API** (client connections), and **LLM backend** (intelligence). The architecture detailed in Clawdbot/Moltbot represents the current state of the art, supporting Discord, Telegram, Slack, Signal, WhatsApp, and iMessage from a single daemon.

**Key insight:** Gateway features fall into three categories:
1. **Table stakes** - Missing these means the gateway doesn't work in production
2. **Differentiators** - Features that provide competitive advantage but aren't expected
3. **Anti-features** - Common mistakes that cause scalability/reliability issues

This research focuses on identifying what must be built first (MVP) vs what can be deferred.

---

## Table Stakes Features

Features users/systems expect. Missing any of these means the gateway feels incomplete or unreliable.

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---------|--------------|------------|--------------|-------|
| **WebSocket transport** | Industry standard for bidirectional streaming | Low | None | HTTP upgrade handshake + message framing |
| **Streaming LLM responses** | Users expect real-time token-by-token output | Medium | WebSocket | Server-Sent Events (SSE) acceptable for read-only clients |
| **Tool calling support** | Clara's existing feature set requires this | Medium | LLM backend | Must support OpenAI-format tools + Anthropic native |
| **Per-channel message queuing** | Prevents concurrent tool execution issues | Medium | Router | Active-mode batching is differentiator, not table stakes |
| **Request cancellation** | Users must be able to interrupt long-running tasks | Low | Router + Task management | "Stop phrases" feature from Discord bot |
| **Session management** | Track which adapter owns which user/channel | Low | Registry | Reconnection support with session resumption |
| **Adapter registration** | Gateway must know what platforms are connected | Low | None | Handshake with capabilities negotiation |
| **Heartbeat/keepalive** | Detect dead connections before TCP timeout | Low | None | Ping/pong every 30s, 10s timeout standard |
| **Error recovery** | Graceful degradation when components fail | Medium | All systems | Errors must not crash gateway or lose messages |
| **Authentication** | Prevent unauthorized gateway access | Low | None | Token-based or challenge-response signing |
| **Memory integration** | Context from mem0 for personalized responses | High | MemoryManager | Already exists in codebase |
| **Multi-user isolation** | Each user's data/context isolated from others | Medium | Memory + Session | Platform-prefixed user IDs (discord-123) |
| **Attachment support** | Users send images/files, gateway must handle | Medium | Protocol + Storage | Base64 encoding for images, file references for large files |
| **Logging/observability** | Debug issues, understand system health | Low | Structured logging | OpenTelemetry optional, basic logs mandatory |

### Critical Path Analysis

For MVP, implement in this order:
1. WebSocket server + registration + heartbeat (core transport)
2. Message routing + queuing (prevents chaos)
3. LLM integration + streaming (value delivery)
4. Tool calling (Clara's differentiator)
5. Memory integration (personalization)
6. Attachment support (user expectation)

Defer: Advanced error recovery patterns (circuit breaker, bulkhead) can come post-MVP.

---

## Differentiators

Features that set this gateway apart. Not expected, but provide competitive advantage.

| Feature | Value Proposition | Complexity | Dependencies | When to Build |
|---------|-------------------|------------|--------------|---------------|
| **Active-mode batching** | In high-volume channels, batch multiple messages into one response | High | Router + Processor | Phase 2 - Discord has this, makes Clara scalable in busy servers |
| **Tier-based model selection** | Route to Opus/Sonnet/Haiku based on complexity | Medium | LLM orchestrator | Phase 1 - Already exists in Discord bot, maintain parity |
| **Event hooks system** | Execute shell commands on gateway events | Medium | Event emitter | Phase 2 - Enables automation without code changes |
| **Task scheduler** | Cron/interval tasks (backups, cleanup) | Medium | Scheduler + Event system | Phase 2 - Operational convenience |
| **Reply chain tracking** | Maintain conversational context from threaded replies | Medium | Message processor | Phase 1 - Discord-specific but valuable |
| **Rich tool status** | LLM-generated descriptions for tool execution | Medium | Tool executor + LLM | Phase 2 - UX polish, not functional requirement |
| **Proactive messages (ORS)** | Gateway can initiate conversations | Medium | Router + Adapter protocol | Phase 3 - Outbound Response System, requires scheduler |
| **Message deduplication** | Idempotent requests via request ID tracking | Low | Router | Phase 1 - Prevents accidental duplicate processing |
| **Queue position tracking** | Tell users where they are in line | Low | Router | Phase 1 - UX feature, trivial to add |
| **Connection pooling** | Reuse DB/API connections across requests | Medium | Database layer | Phase 1 - Performance optimization |
| **Graceful shutdown** | Finish in-flight requests before stopping | Low | Server lifecycle | Phase 1 - Operational requirement |
| **Canvas hosting** | Serve agent-editable HTML interfaces | Low | HTTP server on separate port | Phase 3 - Moltbot feature, niche use case |

### Differentiation Strategy

**Phase 1 (MVP):**
- Tier-based model selection (maintain Discord bot feature parity)
- Reply chain tracking (Discord threads are popular)
- Message deduplication (reliability)
- Queue position tracking (UX)
- Graceful shutdown (ops requirement)

**Phase 2 (Polish):**
- Active-mode batching (scalability for busy channels)
- Event hooks (operational flexibility)
- Task scheduler (automation)
- Rich tool status (UX polish)

**Phase 3 (Advanced):**
- Proactive messages/ORS (requires separate planning)
- Canvas hosting (if needed)

---

## Anti-Features

Features to explicitly NOT build. Common mistakes in bot gateway architectures.

| Anti-Feature | Why Avoid | What to Do Instead | Evidence |
|--------------|-----------|-------------------|----------|
| **Embedding business logic in gateway** | Tight coupling, can't scale independently | Gateway routes messages, business logic in separate services | AWS API Gateway best practices: "gateway should not contain business logic" |
| **Synchronous tool execution** | Blocks response streaming, poor UX | Async tool execution with progress updates | Discord bot currently has this issue |
| **Direct LLM provider coupling** | Vendor lock-in, hard to switch providers | Abstract LLM interface (already done in llm_backends.py) | Clara's multi-provider approach is correct |
| **In-memory only state** | Lost on restart, can't scale horizontally | Externalize session state to Redis or DB | Ably/Clawdbot use Redis for connection metadata |
| **No rate limiting** | Gateway vulnerable to abuse/overload | Per-user, per-channel, global rate limits | Microsoft Bot Framework: HTTP 429 handling mandatory |
| **Manual dependency management** | Manual bottlenecks, slow responses | Use dependency injection, lazy loading | Clawdbot anti-pattern: "manual decision-making bottlenecks" |
| **Unbounded message history** | Memory leak, slow context building | Sliding window + summarization | Discord bot's 25 message limit is reasonable |
| **Polling for updates** | Wasteful, high latency | Push-based WebSocket or SSE | Industry standard: WebSocket for bidirectional, SSE for read-only |
| **Generic chatbot focus** | Commoditized, no defensible moat | Vertical-specific workflows with tool calling | "The era of the generic chatbot is dead" (2026 trends) |
| **Inadequate testing** | Production failures, security gaps | Load testing, chaos engineering | AWS: "Comprehensive performance testing to identify bottlenecks" |
| **Single-threaded processing** | Can't utilize multiple cores | Thread pool or async event loop | Gateway processor uses ThreadPoolExecutor (20 workers default) |
| **No circuit breakers** | Cascading failures when services go down | Circuit breaker + bulkhead patterns | API7.ai: "Circuit breakers prevent cascading issues" |

### Anti-Pattern Prevention

**What NOT to build:**
1. ❌ Business logic in gateway (keep it thin)
2. ❌ Synchronous tool execution (async only)
3. ❌ In-memory session state (externalize to Redis/DB)
4. ❌ No rate limiting (add per-user limits)
5. ❌ Generic chatbot (Clara's tools are the differentiator)

**What to BUILD:**
1. ✅ Gateway as message router + context builder
2. ✅ Async tool execution with streaming status
3. ✅ Session state in PostgreSQL (already done)
4. ✅ Rate limiting middleware (per-user, per-channel)
5. ✅ Tool-first AI assistant (Clara's strength)

---

## Feature Dependencies

Dependency graph showing which features require others:

```
WebSocket Server (core)
  ├─> Adapter Registration
  │   └─> Session Management
  │       └─> Multi-user Isolation
  ├─> Heartbeat/Keepalive
  └─> Authentication

Message Router
  ├─> Per-channel Queuing
  │   ├─> Request Cancellation
  │   └─> Active-mode Batching (differentiator)
  └─> Message Deduplication

LLM Integration
  ├─> Streaming Responses
  ├─> Tool Calling
  │   ├─> Tool Status Updates
  │   └─> Rich Tool Descriptions (differentiator)
  └─> Tier-based Model Selection (differentiator)

Memory Integration
  ├─> Reply Chain Tracking
  └─> Multi-user Isolation

Event System
  ├─> Event Hooks (differentiator)
  └─> Task Scheduler (differentiator)
      └─> Proactive Messages/ORS (differentiator)

Observability
  └─> Logging/Metrics
      └─> OpenTelemetry (optional)
```

**Critical path for MVP:**
1. WebSocket Server → Message Router → LLM Integration → Memory Integration
2. Tool Calling depends on LLM Integration
3. Differentiators (batching, hooks, scheduler) can be added incrementally

---

## MVP Recommendation

For MVP (first production deployment), prioritize:

### Phase 1: Core Gateway (2 weeks)
1. **WebSocket server** - Accept adapter connections
2. **Registration + heartbeat** - Track connected adapters
3. **Message router** - Per-channel queuing
4. **LLM integration** - Streaming responses
5. **Memory integration** - Context from mem0
6. **Tool calling** - Execute Clara's existing tools
7. **Attachment support** - Images + files
8. **Authentication** - Shared secret or token

**Validation:** Discord adapter can connect, send messages, receive streaming responses with tool execution.

### Phase 2: Production Hardening (1 week)
9. **Error recovery** - Graceful degradation
10. **Logging/observability** - Structured logs
11. **Graceful shutdown** - Finish in-flight requests
12. **Rate limiting** - Per-user, per-channel
13. **Connection pooling** - Optimize DB/API usage

**Validation:** Gateway survives adapter crashes, handles overload gracefully, logs useful debugging info.

### Phase 3: Differentiators (2 weeks)
14. **Active-mode batching** - High-volume channel optimization
15. **Event hooks** - Automation on gateway events
16. **Task scheduler** - Cron/interval tasks
17. **Rich tool status** - LLM-generated descriptions

**Validation:** Gateway scales to 100+ concurrent users, supports operational automation.

### Defer to Post-MVP
- Circuit breaker + bulkhead patterns (add when scaling issues arise)
- OpenTelemetry tracing (basic logs sufficient for MVP)
- Canvas hosting (niche feature)
- Proactive messages/ORS (requires separate planning phase)

---

## Technology Recommendations

Based on research into production systems:

### Message Transport
- **WebSocket:** `websockets` library (Python) - Already in use
- **Why not SSE:** Bidirectional communication required for tool calling

### State Management
- **Session state:** PostgreSQL (already in use)
- **Connection metadata:** In-memory for MVP, Redis for scale
- **Why not in-memory only:** Anti-pattern - can't scale horizontally

### Message Broker (Future)
- **For MVP:** Direct async processing (no broker needed)
- **For scale:** Redis Streams or RabbitMQ
- **When:** When queue depth > 1000 or cross-gateway communication needed

### Observability
- **MVP:** Structured logging to stdout (already done)
- **Production:** OpenTelemetry + metrics exporter
- **Tools:** Prometheus (metrics), Grafana (dashboards)

### Resilience Patterns
- **Circuit breaker:** Resilience4j pattern, implement post-MVP
- **Rate limiting:** Token bucket algorithm, per-user + per-channel
- **Retry logic:** Exponential backoff with jitter for LLM/tool calls

---

## Complexity Analysis

| Feature Category | Total Features | Low Complexity | Medium Complexity | High Complexity |
|------------------|----------------|----------------|-------------------|-----------------|
| Table Stakes | 14 | 5 | 7 | 2 |
| Differentiators | 11 | 3 | 7 | 1 |
| Anti-features | 12 | - | - | - |

**Complexity distribution:**
- **Low:** 8 features (57% of MVP)
- **Medium:** 14 features (can be parallelized)
- **High:** 3 features (memory integration, active-mode batching, tool calling)

**Risk areas:**
1. Memory integration (high complexity, critical path)
2. Tool calling (medium-high, lots of edge cases)
3. Active-mode batching (high complexity, can defer)

---

## Sources

### Architecture Examples
- [Clawdbot/Moltbot Architecture](https://docs.molt.bot/concepts/architecture) - Three-layer gateway architecture with WebSocket transport
- [Clawdbot Complete Guide 2026](https://www.godofprompt.ai/blog/clawdbot-guide-2026) - Multi-platform bot gateway features and patterns
- [WTH is Clawdbot - DEV Community](https://dev.to/asad1/wth-is-clawdbot-building-your-own-cross-platform-ai-assistant-with-clawdbot-in-2026-4non) - Cross-platform AI assistant architecture

### WebSocket Best Practices
- [WebSocket Gateway Reference Architecture - DASMETA](https://www.dasmeta.com/docs/solutions/websocket-gateway-reference-architecture/index) - Gateway architecture patterns for scalability
- [How to scale WebSockets - Ably](https://ably.com/topic/the-challenge-of-scaling-websockets) - High-concurrency WebSocket scaling
- [Node.js and Websockets best practices - Voodoo Engineering](https://medium.com/voodoo-engineering/websockets-on-production-with-node-js-bdc82d07bb9f) - Production WebSocket checklist
- [WebSockets at Scale - WebSocket.org](https://websocket.org/guides/websockets-at-scale/) - Production architecture and best practices

### Rate Limiting & Queuing
- [Rate limiting for bots - Microsoft Teams](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/how-to/rate-limit) - Bot Framework rate limiting patterns
- [API Rate Limiting 2026 - Levo.ai](https://www.levo.ai/resources/blogs/api-rate-limiting-guide-2026) - Modern rate limiting approaches
- [Redis vs RabbitMQ - Airbyte](https://airbyte.com/data-engineering-resources/redis-vs-rabbitmq) - Message broker comparison for bot systems
- [Modern Queueing Architectures - Medium](https://medium.com/@pranavprakash4777/modern-queueing-architectures-celery-rabbitmq-redis-or-temporal-f93ea7c526ec) - Queue architecture patterns for 2026

### LLM Streaming & Tool Calling
- [Streaming LLM responses WebSocket - Deepgram](https://developers.deepgram.com/docs/send-llm-outputs-to-the-tts-web-socket) - WebSocket streaming patterns for LLM output
- [Building Real-Time AI Chat - Render](https://render.com/articles/real-time-ai-chat-websockets-infrastructure) - Infrastructure for WebSocket LLM streaming
- [Streaming AI Responses comparison - Medium](https://medium.com/@pranavprakash4777/streaming-ai-responses-with-websockets-sse-and-grpc-which-one-wins-a481cab403d3) - WebSocket vs SSE vs gRPC for LLM streaming
- [How to stream LLM responses - AWS](https://amlanscloud.com/llmstreampost/) - AWS API Gateway + Lambda streaming architecture

### Memory & Context Management
- [Conversational Memory for LLMs - Pinecone](https://www.pinecone.io/learn/series/langchain/langchain-conversational-memory/) - Memory patterns for conversational AI
- [Mem0: Production-Ready AI Agents - arXiv](https://arxiv.org/pdf/2504.19413) - Scalable long-term memory architecture
- [Context Engineering for Personalization - OpenAI](https://cookbook.openai.com/examples/agents_sdk/context_personalization) - State management with long-term memory
- [ChatGPT Memory Project - Redis](https://redis.io/blog/chatgpt-memory-project/) - Vector database for conversation history

### Anti-Patterns & Resilience
- [Hardening RAG chatbot architecture - AWS](https://aws.amazon.com/blogs/security/hardening-the-rag-chatbot-architecture-powered-by-amazon-bedrock-blueprint-for-secure-design-and-anti-pattern-migration/) - Security and anti-pattern mitigation
- [Top 5 AI Gateways for 2026 - Maxim](https://www.getmaxim.ai/articles/top-5-ai-gateways-for-2026/) - Gateway performance benchmarks (11µs overhead at 5K req/s)
- [Solving Chatbot Scalability Issues - BizBot](https://bizbot.com/blog/solving-chatbot-scalability-issues/) - Common bottlenecks and solutions
- [Circuit Breaker Pattern - API7.ai](https://api7.ai/blog/10-common-api-resilience-design-patterns) - API resilience patterns for 2026
- [Building Resilient Systems 2026 - DasRoot](https://dasroot.net/posts/2026/01/building-resilient-systems-circuit-breakers-retry-patterns/) - Circuit breakers and retry patterns

### Observability
- [LLM Observability with OpenTelemetry](https://opentelemetry.io/blog/2024/llm-observability/) - Observability for LLM applications
- [Can OpenTelemetry Save Observability in 2026 - The New Stack](https://thenewstack.io/can-opentelemetry-save-observability-in-2026/) - OpenTelemetry as industry standard
- [AI Agents Observability - VictoriaMetrics](https://victoriametrics.com/blog/ai-agents-observability/) - Metrics and traces for AI agents

### Fault Tolerance
- [Graceful degradation - AWS](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_mitigate_interaction_failure_graceful_degradation.html) - Transform hard dependencies into soft dependencies
- [Fault tolerance - Ably](https://ably.com/docs/platform/architecture/fault-tolerance) - Real-time platform fault tolerance patterns
- [Graceful degradation explained - DEV Community](https://dev.to/teclearn/web-theory-part-8-graceful-degradation-soft-failure-and-fault-tolerance-explained-7n0) - Soft failure vs fault tolerance

---

## Confidence Assessment

| Research Area | Confidence | Rationale |
|--------------|------------|-----------|
| Table stakes features | HIGH | Verified against 3+ production systems (Clawdbot, Microsoft Bot Framework, AWS API Gateway) |
| Differentiators | MEDIUM-HIGH | Based on competitive analysis + existing Discord bot features |
| Anti-features | HIGH | Documented failures in AWS/Microsoft best practices guides |
| Complexity estimates | MEDIUM | Based on existing Clara codebase inspection |
| Technology choices | HIGH | Already validated in production (WebSocket, PostgreSQL, mem0) |
| MVP scope | MEDIUM | Requires validation with actual development timeline |

**Low confidence areas:**
- Exact timeline estimates (need real-world testing)
- Load characteristics (concurrent user counts, message volume)
- Edge cases in active-mode batching (high complexity feature)

**Gaps to address:**
- Load testing to validate capacity assumptions
- Security audit of WebSocket authentication
- Circuit breaker pattern implementation details (defer to when needed)

---

## Open Questions

1. **Rate limiting thresholds:** What are appropriate per-user/per-channel limits? Need production data.
2. **Redis vs in-memory:** At what scale does in-memory session state become a bottleneck?
3. **Circuit breaker tuning:** What error rate triggers circuit open? Need load testing.
4. **Batch size limits:** How many messages can be batched before response quality degrades?
5. **WebSocket connection limits:** How many concurrent adapters can one gateway handle?

**Recommendation:** Start with MVP (no Redis, no circuit breaker), measure in production, add complexity when actual bottlenecks appear.
