# Unified Ambient Reflection — Design

**Date:** 2026-06-14
**Status:** Approved (design). Next: implementation plan.
**Implementation repo:** **`mypal-engine`** (engine). The mypalclara slice is minimal and deferred (persona reflection framing).
**Relates to:** [`2026-06-14-galadriel-features-reconciliation.md`](./2026-06-14-galadriel-features-reconciliation.md) (this is feature #1, the centerpiece) and the [experience charter](./2026-06-05-mypalclara-experience-charter-design.md) (intelligence → engine).

## Goal

Give Clara a single **ambient system** that runs between conversations: she reflects inward (consolidates memory, develops a continuous thread of thought) and, on a separate high bar, reaches outward (surfaces something to the user). This **replaces ORS** (deleted — it never worked) and **absorbs the heartbeat** (the only live proactive loop today), so the end state is **one** background loop, not three.

The central design constraint: a **firewall** between inward and outward, so reflecting never automatically becomes speaking — that's what ORS got wrong.

## Decisions (from the brainstorm)

| Question | Decision |
|---|---|
| Primary job | **Both, balanced** — genuine inner life *and* well-timed outreach, explicitly separated. |
| Trigger | **Fixed cron**, in each user's waking hours (their timezone). Not interval, not adaptive (adaptive is what ORS did). |
| Continuity | **Dated journal + memory extraction.** A readable train of thought re-read each turn, plus durable facts into the Palace. |
| Surfacing | **Hybrid** — queue by default (woven into next conversation), urgent → unsolicited DM (active-hours + min-gap gated). |
| Scope | **Owner + opted-in users.** Per-user opt-in flag + per-user timezone. Not all active users. |
| Loop shape | **Approach A — one turn, two phases.** Firewall = the phase boundary. |

## Architecture (Approach A)

A single per-user **ambient turn**, fired by the existing `gateway/scheduler.py` `Scheduler` on a fixed cron computed for each opted-in user's timezone. Each turn runs two phases:

1. **Phase 1 — Reflect** (always runs): a *silent, tool-enabled* agent turn. Reads recent journal + relevant memory, consolidates, appends a dated journal entry, extracts durable memories. **Structurally cannot message the user** (no adapter emission path).
2. **Phase 2 — Surface gate** (separate, cheap, structured-output call): given Phase 1's reflection + light context, returns `nothing | queue | urgent`. Only this phase can reach the user.

**The firewall is the phase boundary.** Phase 1 has no delivery capability; speaking requires an explicit Phase-2 decision that clears a high bar.

## Components (engine)

- **`mypalclara/ambient/` (new module)** — replaces both `core/heartbeat.py` and `services/proactive/`. Contains:
  - `ambient_turn(user_id)` — orchestrates Phase 1 → Phase 2 for one user, applies guards.
  - `reflect(user_id)` — Phase 1.
  - `surface_gate(user_id, reflection)` — Phase 2.
  - per-user cron registration against the `Scheduler`.
- **Silent turn** — extend `LLMOrchestrator.generate_with_tools()` (`gateway/llm_orchestrator.py:110`) with a *silent mode*: run the real tool loop but suppress `ResponseStart/ResponseChunk/ResponseEnd` to adapters and return final text + tool results. **Reuse over fork** — reflection quality equals real-turn quality, and the loop never diverges. (Exact mechanism — flag vs. injected emitter — decided in the plan.)
- **Reflection toolset** — a curated allowlist: read/append journal, memory search, memory write/extract, read-only calendar/files. **Excludes** terminal, browser, and any destructive/mutating tools.
- **Journal** — dated per-user markdown in the user's workspace; Phase 1 reads the last N days for continuity. (Reuses the engine's per-user files/workspace infra — exact path confirmed in the plan.)
- **`SurfacedThought` queue** — new DB model (below); injected into context on the user's next message.
- **Outreach delivery** — urgent DMs reuse the existing `ProactiveMessage` WS path (the `_heartbeat_send`-style sender in `gateway/__main__.py`).

## Persistence & config

**New DB:**
- `SurfacedThought` — `id, user_id, content, kind (queue|urgent), created_at, surfaced_at, expires_at, delivered`.
- `AmbientUserConfig` (new small table) — `user_id, reflection_opt_in (bool), timezone (IANA str)`. (A field on an existing user table instead, if a clean one exists — plan-time.)

Both via Alembic `revision --autogenerate`.

**New envs:**
- `AMBIENT_ENABLED` (master switch)
- `AMBIENT_CRON` — default **`0 11,14,17,20 * * *`** (waking-hours cadence, per-user timezone)
- `AMBIENT_REFLECT_TOKEN_BUDGET` — Phase-1 per-turn cap
- `AMBIENT_MIN_DM_GAP_HOURS` — min gap between unsolicited DMs
- `AMBIENT_JOURNAL_READBACK_DAYS` — days of journal Phase 1 re-reads
- `AMBIENT_RECENT_ACTIVITY_SKIP_MIN` — skip a turn if the user messaged this recently

**Removed:** all `ORS_*`; `HEARTBEAT_*` retired/folded.

## Data flow

1. **Startup** — for each opted-in user, register a per-user cron task (computed from their timezone) on the `Scheduler`; handler = `ambient_turn(user_id)`.
2. **Tick → `ambient_turn`:**
   - **Guard:** if the user messaged within `AMBIENT_RECENT_ACTIVITY_SKIP_MIN`, skip (don't reflect over their shoulder).
   - **Phase 1 Reflect:** silent, token-budgeted turn → journal append + memory writes.
   - **Phase 2 Surface gate:** structured decision —
     - `nothing` → done.
     - `queue` → insert `SurfacedThought(kind=queue)`.
     - `urgent` → if active-hours **and** past `AMBIENT_MIN_DM_GAP_HOURS` → send DM + record; **else downgrade to queue**.
3. **Next user message** — `MessageProcessor._build_context()` (`gateway/processor.py`) pulls undelivered `SurfacedThought`s for the user, injects them so Clara raises them naturally, and marks them delivered. Honors `expires_at` (stale thoughts are dropped, not surfaced).

## ORS retirement + heartbeat absorption (folded into this build)

- **Delete** `mypalclara/services/proactive/` (`engine.py` + `__init__.py`).
- **Drop** `ProactiveNote`, `ProactiveAssessment`, `UserInteractionPattern` (+ the `contact_cadence_days` column from migration `h8i9j0k1l2m3`) via a new down-migration. **Keep `ProactiveMessage`** (still used by delivery + history).
- **Remove** all `ORS_*` / `PROACTIVE_*` config from `.env*` and config modules; remove ORS tests/docs.
- **Delete** `core/heartbeat.py` and its startup wiring in `gateway/__main__.py`; its "should I ping?" role becomes Phase 2. `HEARTBEAT.md` is **dropped** (its intent is absorbed into the reflection prompt).
- Confirm architecture/import tests stay green.

## Guards (the anti-ORS layer)

- Recent-activity skip (don't reflect/surface while the user is active).
- Per-turn token budget on Phase 1.
- Min-gap **and** active-hours-only on unsolicited DMs.
- Queue staleness/expiry — never surface a stale thought.
- The cron itself rate-limits the loop (no runaway reflection).
- Tool allowlist excludes destructive/mutating ops in silent turns.

## Error handling

- Each phase is isolated. A failed Phase 1 logs and aborts the turn (no Phase 2 on a bad reflection). A failed Phase 2 logs and sends nothing. The `Scheduler` already isolates task errors. Silent-turn tool errors fall under the existing tool guards/result caps.

## Testing

- **Unit:** `surface_gate` decisions (nothing/queue/urgent); every guard (recent-activity skip, min-gap, active-hours, staleness); journal read/write; opt-in filtering; timezone → cron computation.
- **Integration:** a full `ambient_turn` with a stubbed LLM (reflect → journal + memory; gate → queue and DM paths); `SurfacedThought` injection on the next message; expiry drop.
- **Invariant:** assert the silent turn emits **nothing** to adapters.
- **Regression:** architecture/import tests green after ORS deletion.

## Client slice (mypalclara — deferred)

- Persona-specific reflection framing (Clara / Flo / Clarissa) — the Phase-1 reflection prompt can vary per persona; lives with the personas. Minor follow-up.
- **No new protocol** — urgent DMs reuse `ProactiveMessage`; queued thoughts are engine-internal context injection.

## Non-goals (v1)

- All-active-users reflection (scoped to owner + opted-in).
- Adaptive cadence (fixed cron only).
- Carrying ORS's schema, state machine, or notes machinery (clean-slate; re-implement any wanted capability leanly).
- An interactive approval/safety round-trip (that's the separate Safety Tiers feature).

## Deferred to the plan

- Exact silent-mode mechanism in `generate_with_tools` (flag vs. injected emitter).
- Journal storage path within the per-user workspace/sandbox.
- Whether opt-in/timezone is a new `AmbientUserConfig` table or a field on an existing user record.
- Final Phase-1 tool allowlist membership.
- Active-hours derivation (from `AMBIENT_CRON` window vs. an explicit per-user active-hours range).
