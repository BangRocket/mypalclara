# Galadriel Features — Reconciliation & Gap Analysis

**Date:** 2026-06-14
**Status:** Reconciliation (inventory). Not a design. Each surviving feature gets its own design → plan → build cycle.
**Relates to:** [`2026-06-05-mypalclara-experience-charter-design.md`](./2026-06-05-mypalclara-experience-charter-design.md). This is a new cross-cutting initiative ("Clara continuity / inner life") that sits alongside roadmap items #1–#6, not inside them.
**Reference spec:** "Clara Enhancement Spec: Galadriel Features" (Ambient Reflection · Local Semantic Memory · One-Shot Wake · Safety Tiers), porting from `github.com/avasol/galadriel-public`.

## Why this document exists

The reference spec is written as if porting into a greenfield. It is not greenfield. Most of the machinery it describes **already exists in `mypal-engine`** (verified locally at `/Volumes/Storage/Code/mypal-engine`, on the `mypalclara/` package path inside that repo). And per the experience-layer charter, almost all of this work is *intelligence* → it lands in the engine, not in this client repo. The client's only legitimate slices are the user-facing surfaces.

This doc reconciles each feature against (a) what is already built, verified by reading the code, and (b) the engine/experience split the charter mandates — so we design only the real gaps, in the right repo.

## The charter lens

The "does it belong here?" test from the charter: *intelligence → engine; first-party surface a user experiences → mypalclara.*

- **Engine (`mypal-engine`):** reflection turns, memory/Palace, wake persistence, safety classification + gating, scheduling. All of it.
- **mypalclara (this repo):** only the experience touchpoints — how a reflection or wake *appears* to the user, persona-specific reflection framing, and the **approval round-trip** a safety gate needs (protocol + adapter handler + Discord view wiring).

Net: this is ~85% engine work. The client slices are small but real (and one of them — the safety approval round-trip — is genuinely missing today).

## Cross-cutting facts (verified)

- **Agent turn loop:** `mypalclara/gateway/processor.py` → `MessageProcessor.process()` builds context and calls `LLMOrchestrator.generate_with_tools()` (`gateway/llm_orchestrator.py:110`), a multi-turn tool loop (max 75 iterations). It **always** emits `ResponseStart → ResponseChunk* → ResponseEnd` (built at `processor.py:405` and `:518`). There is **no "silent turn"** path that runs the tool loop without posting output.
- **Scheduler:** `gateway/scheduler.py` — `TaskType` = `ONE_SHOT | INTERVAL | CRON`, real cron parser, Python-handler callables (`handler: Callable[...]`), `run_at`/`delay` for one-shots. Loaded from `scheduler.yaml` at startup. **Cron cadence is already available.**
- **Two proactive systems exist — one live, one dead:**
  - `core/heartbeat.py` — **LIVE** (`HEARTBEAT_ENABLED=true` in `.env`). Periodic *silent* per-active-user LLM check, `HEARTBEAT.md`-driven, `is_ack()` decides whether to surface, delivers via a `send_fn` over WebSocket. **Bare LLM call — no tools, no memory writes.** Interval-based (`HEARTBEAT_INTERVAL_MINUTES`, default 30).
  - `services/proactive/engine.py` — the 77KB **ORS** (Organic Response System): WAIT/THINK/SPEAK, decaying notes, assessments, timezone/active-hours, Google Calendar, learned patterns, idle-conversation learning. **ORPHANED & DEAD:** `ORS_ENABLED=false`, *never wired into `gateway/__main__.py`*, **zero external callers** (only its own `__init__.py` re-exports). Per the owner: it never worked right. **Slated for full deletion** — see "ORS retirement" below.
- **Proactive delivery is fully wired client↔engine:** protocol `ProactiveMessage`; `GatewayClient.on_proactive_message()` in `mypalclara/adapters/base.py`; Discord delivers via DM with channel fallback.
- **Boundary:** `tests/architecture/test_engine_boundary.py` forbids adapters from importing any engine package — client reaches the engine only via `mypal_protocol` (WS) and `EngineApiClient` (HTTP).
- **Persistence:** engine uses SQLAlchemy models in `db/models.py` + Alembic migrations in `db/migrations/versions/`. New tables follow `alembic revision --autogenerate`.

---

## Feature 1 — Ambient Reflection

**Spec intent:** scheduled silent turns where Clara consolidates/reflects (using tools, writing memory), output to memory/workspace, surfaced to the user only if worth it.

**Already exists:** the *scheduling* (`scheduler.py`, cron) and a *silent-check + surface-if-needed* loop (`heartbeat.py`), plus a delivery path (`ProactiveMessage`).

**Real gap:**
1. Heartbeat runs a **bare LLM call**, not the tool-enabled agent turn. Reflection's whole point is *consolidation into memory* — it needs `generate_with_tools()` (or equivalent) with memory/Palace tools available, output suppressed from chat. **No silent tool-enabled turn mode exists.** This is the core new build.
2. A **reflection system prompt** distinct from heartbeat's "should I ping?" framing.
3. **Cron cadence** wiring (11/14/17/20 workday pattern) — plumbing exists; needs configuring + per-user timezone.
4. **Guards:** skip if user recently active; rate-limit; per-turn token budget. (Heartbeat has none of these.)

**Consolidation directive (DECIDED — the headline of this initiative):** this is the chance to **put ORS to bed.** ORS is deleted outright (orphaned, never worked — see "ORS retirement"). Ambient Reflection becomes **the single ambient system**, and it **subsumes heartbeat** too: heartbeat's "should I ping this user?" check becomes one *cheap* mode of the reflection loop, not a separate bare-LLM loop. **End state = one background loop, not three.** The new system is designed clean — it does **not** inherit ORS's schema, state machine, or notes machinery; if it wants a capability ORS had (timezone/active-hours, calendar, learned cadence), it designs its own leaner version.

**Split by concern:**
- *Engine:* silent tool-enabled turn, reflection prompt, cron wiring, guards, memory-write path.
- *mypalclara:* persona-specific reflection framing (`personalities/`); how a *surfaced* reflection appears (low-priority `ProactiveMessage` vs normal message) — minor, mostly already handled.

**Verdict:** **BUILD — the centerpiece of this initiative.** The mechanism is narrower than the spec reads (a silent tool-enabled turn mode + reflection prompt + cron cadence + guards, reusing the existing scheduler and delivery path), but the *framing* is the big one: it's the unified ambient system that **replaces ORS and absorbs heartbeat.** Highest design effort, but the payoff is going from three half-built loops to one that works.

---

## ORS retirement (lose all weight)

Independent, safe, and high-value on its own — ORS is orphaned dead code that never worked. Can land as a standalone `refactor:`/`chore:` change **before** the reflection build (clears the deck), since nothing depends on it.

**Confirmed safe to delete (verified):** `ORS_ENABLED=false`; not started in `gateway/__main__.py`; zero importers outside `services/proactive/` itself; its 3 exclusive DB models have no non-ORS readers/writers (so the tables are almost certainly empty — ORS never ran).

**Removal checklist (engine repo):**
- Delete `mypalclara/services/proactive/` (`engine.py` + `__init__.py`).
- Drop the 3 ORS-only models in `db/models.py` — `ProactiveNote`, `ProactiveAssessment`, `UserInteractionPattern` (plus the `contact_cadence_days` column from migration `h8i9j0k1l2m3`) — via a new Alembic down-migration. **Keep `ProactiveMessage`** (still used by heartbeat's delivery + history).
- Remove `ORS_*` / `PROACTIVE_*` config from `.env*` and any config module.
- Remove ORS tests and any doc references.
- Confirm the architecture/import tests still pass.

**Carry-forward (ideas, not code):** if the new reflection system wants them, re-implement leanly — timezone/active-hours awareness, optional calendar context, a notion of "open threads / follow-ups," and contact cadence. Decide each in the Ambient Reflection brainstorm; do not port ORS's implementations.

---

## Feature 2 — Local Semantic Memory

**Spec intent:** zero-cost local vector search so retrieval isn't a token tradeoff.

**Already exists — substantially the whole feature.**
- Vector stores: `core/memory/vector/{qdrant.py,pgvector.py}`.
- **Embeddings already default to local:** `EMBEDDING_PROVIDER` defaults to **`huggingface`** (`core/memory/config.py:306`), dims 1024 (e5-large-v2). OpenAI embeddings are opt-in only. So "zero-cost local vectors" is already the default path.
- Episodic semantic search, layered L0–L3 retrieval, and agent memory tools (`core/core_tools/memory_visibility_tool.py`) all exist.

**Real (small) gap:**
- The residual *cost* in the memory path is **not** embeddings — it's the extraction LLM (`PALACE_MODEL`, default `openai/gpt-4o-mini`, `config.py:107`) and, when `USE_PALACE_SERVICE=true`, the **remote-Palace HTTP round-trip** (`core/memory/routed.py`, `mypalace_client.PalaceClient`).
- So the only thing resembling the spec's ask is: ensure a **fully-local, embedded retrieval path** (`USE_PALACE_SERVICE=false`) and optionally expose a cheap **exhaustive local search tool** the agent can call freely.

**Split by concern:** essentially all engine-internal; ~zero client work (an optional `/memory search` adapter surface at most).

**Verdict:** **MOSTLY SATISFIED — do not rebuild.** Reframe to a small optional task: "confirm/enable fully-local retrieval + add an exhaustive local-search tool." Galadriel's ChromaDB/MemPalace is redundant with the existing Qdrant/Palace stack. **Drop ChromaDB.**

---

## Feature 3 — One-Shot Wake

**Spec intent:** a restart-surviving self-prompt that fires once on startup as a synthetic user message.

**Already exists:** scheduler one-shot tasks (`run_at`/`delay`) — but **in-memory**, lost on restart. Startup lifecycle has a `GATEWAY_STARTUP` event/hook point.

**Real gap (genuinely new, small, self-contained):**
1. A **persisted** wake: new DB model (`user_id`, `prompt`, `armed_at`, `fire_after?`, `fired`) + Alembic migration.
2. A **`wake_arm` agent tool** to set one.
3. A **startup check** that fires armed, non-stale wakes as synthetic user messages through the normal turn path, then marks them fired.
4. Staleness cutoff (don't fire a 3-day-old wake).

**Split by concern:**
- *Engine:* the whole mechanism (model, tool, startup hook, staleness). The fired wake flows through the existing turn → `ResponseEnd` → delivery path, so no new delivery work.
- *mypalclara:* effectively none. (Optional: an "armed wake" indicator — skip for v1.)

**Verdict:** **BUILD FIRST.** Smallest, most self-contained, high continuity value, near-zero client surface, no reconciliation tangles. Good warm-up (matches the spec's own instinct).

---

## Feature 4 — Safety Tiers

**Spec intent:** classify operations green/yellow/red; red requires Discord approve/deny before proceeding.

**Already exists (partial, and overstated by the spec):**
- *Rendering* of buttons end-to-end: protocol `ButtonInfo` / `ResponseEnd.components`; Discord `GatewayButtonView` / `ConfirmView`; an agent tool to emit buttons (`gateway/tool_executor.py`).
- Scattered safety primitives: `core/security/{circuit_breaker,injection_scanner,sandboxing}.py`, `core/tool_guard.py` (loop detection), `core/security/worm_persona.py` (coarse classifier).

**Real gap (two parts):**
1. **No classifier/gate before tool execution.** `ToolExecutor` runs tools unconditionally. Need an `OperationClassifier` (green/yellow/red rubric) + a gate that pauses red ops.
2. **The existing buttons are cosmetic — there is NO approval round-trip.** `dismiss` just removes buttons; `confirm` just edits the message text. Nothing sends the user's decision back to a *paused* engine operation. A real red-tier gate needs a **new protocol message pair** (approval request → approval response) + a mechanism to suspend/resume a gated tool call. This is the actual meat, and it's the one place the **client** has real new work (protocol + `on_approval_request` handler + a blocking Discord view that returns the decision).

**Split by concern:**
- *Engine:* classifier, rubric, gate/suspend-resume, audit log, approval-request protocol emission, timeout.
- *mypalclara:* approval-request protocol handler in `GatewayClient`; a Discord view that **returns** approve/deny to the engine (not just edits the message); timeout UX.

**Verdict:** **BUILD LAST (or when an interactive-approval round-trip is independently wanted).** Lower value per the spec; the reusable piece is the approval round-trip, which other features could share. "UI already exists" is only half-true — budget for the round-trip.

---

## Revised priority & order

The spec's instinct (Wake → Reflection → Memory → Safety) mostly holds, but the reframe changes effort and drops one:

| Order | Feature | Verdict | Where the work is | Effort vs spec |
|---|---|---|---|---|
| 0 | **ORS retirement** | Delete now | Engine (delete pkg + drop 3 models + config) | New scope — safe dead-code removal, lands independently |
| 1 | **One-Shot Wake** | Build | Engine (DB+tool+startup); ~0 client | As specified — small |
| 2 | **Ambient Reflection** | Build — **centerpiece** | Engine (silent tool-turn+prompt+cron+guards, replaces ORS, absorbs heartbeat); persona framing in client | Mechanism **smaller** (reuses scheduler/delivery); framing is the big design |
| 3 | **Safety Tiers** | Build last / on demand | Engine (classifier+gate) + client (approval round-trip) | **Larger than "UI exists"** — round-trip is new |
| — | **Local Semantic Memory** | Mostly satisfied — don't rebuild | Engine-only small task; drop ChromaDB | **Dropped to optional** |

## Open questions to resolve per-feature (in each one's own brainstorm)

- **Reflection:** the three-proactive-systems reconciliation (extend heartbeat / fold into ORS THINK / distinct loop?); the reflection prompt; per-user vs global; where surfaced reflections live (workspace daily-note? memory only?).
- **Wake:** per-user vs global; staleness cutoff value; what counts as a "restart" worth surviving.
- **Safety:** the green/yellow/red rubric; approval timeout; whether the approval round-trip is built as shared infra first.
- **Memory:** is the residual ask just "force `USE_PALACE_SERVICE=false` + an exhaustive local search tool," or is there a real complaint about current retrieval quality/cost we should measure first?

## Next step

**ORS retirement** (order 0) can land immediately as a standalone cleanup — it's safe dead-code removal and clears the deck. Then brainstorm the new feature work. Open sequencing choice: **Ambient Reflection** (the ORS replacement, where the energy is) vs **One-Shot Wake** (smaller warm-up) first. Memory stays out of scope unless a concrete retrieval complaint surfaces.
