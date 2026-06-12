# Discord Channel Monitor — Scheduled Summaries + Semantic Issue Flagging

**Status:** Design (no code yet)
**Date:** 2026-06-12
**Author:** Clara / Claude Code
**Repos affected:** `mypal-engine` (analysis + scheduling), `mypalclara` (Discord delivery + config)

---

## 1. Goal

Give server admins a bot that watches a Discord channel (or set of channels) and, on a
schedule, produces **two independent outputs**:

1. **Activity digest** — "here's what members have been talking about" (topics, themes,
   notable threads, activity level). Posted to a configured **digest channel**.
2. **Semantic issue scan** — a *separate* pass that hunts for problems: conflicts between
   members, unresolved complaints, confusion/blockers, escalating negativity, possible
   moderation concerns. Each finding is a structured **flag** delivered **privately to
   admins** (admin channel or DM), independent of the digest.

The two outputs are deliberately decoupled: the digest is a friendly public summary; the
flags are a private heads-up that should never be diluted by — or buried inside — the
digest.

## 2. Background: this used to (mostly) exist

Before the client/engine split (commit `da1ec35`, "feat(cut): trim mypalclara to
client-only", 2026-06-04, at version `2026.19.2`), MyPalClara contained nearly all the
machinery this feature needs. The cut moved it into `mypal-engine` because it depends on
the LLM, database, and Palace memory — none of which exist in this client repo anymore.

Reusable prior art (recoverable from history before `da1ec35`, now engine-side):

| Pre-cut file | What it did | Reuse for |
|---|---|---|
| `gateway/channel_summaries.py` | Time-windowed LLM channel summarization (old msgs summarized, recent kept verbatim, incremental updates, `ChannelSummary` DB model) | **Activity digest** |
| `gateway/scheduler.py` (729 lines) | Background scheduling loop | **The schedule** |
| `core/heartbeat.py` (212 lines) | Periodic background tick | Scheduler heartbeat |
| `core/sentiment.py` | VADER rule-based sentiment scoring (no LLM, fast) | **Cheap pre-filter** for the issue scan |
| `core/memory/context/topics.py` (588 lines) | LLM topic extraction + recurrence / sentiment-trend tracking | **Topic extraction + drift detection** |
| `core/memory/context/emotional.py` (325 lines) | Emotional-arc tracking | Conflict/tone context |
| `services/proactive/engine.py` (2033 lines) + ORS | Autonomous "speak when there's genuine reason, not on a schedule" system | Reference for the assessment/decision pattern |

> **Note on "Clara replies automatically based on context":** that lives on today as the
> `active` channel mode (`mypalclara/adapters/discord/channel_modes.py`), which is
> *reactive* and *per-message*. It is **not** the same as scheduled monitoring, but it
> shares the "read the room" instinct. The monitor is the scheduled, observe-only sibling.

## 3. Architecture overview

```
                          mypal-engine (analysis + scheduling)
   ┌───────────────────────────────────────────────────────────────────┐
   │  ChannelMonitorScheduler  (resurrected scheduler.py + heartbeat)   │
   │      │  every N minutes, per monitored channel                     │
   │      ▼                                                             │
   │  fetch recent messages ──▶ VADER pre-filter (sentiment.py)         │
   │      │                          │                                  │
   │      ▼                          ▼                                  │
   │  Digest pass (LLM)         Issue-scan pass (LLM, only if warranted)│
   │  topics + activity         structured flags (severity/who/quote)   │
   │      │                          │                                  │
   │      └────────────┬─────────────┘                                  │
   │                   ▼                                                │
   │         emit ProactiveMessage(s) over Gateway WS  ─────────────────┼──┐
   └───────────────────────────────────────────────────────────────────┘  │
                                                                           │
                          mypalclara (this repo — Discord delivery)        │
   ┌───────────────────────────────────────────────────────────────────┐  │
   │  DiscordGatewayClient.on_proactive_message  (already exists)  ◀────────┘
   │      digest  → digest channel (normal priority)                   │
   │      flags   → admin channel / DM (high priority, distinct embed)  │
   │                                                                    │
   │  Config: monitored channels + targets via EngineApiClient (HTTP)   │
   │  Admin slash commands to enable/disable + set targets              │
   └───────────────────────────────────────────────────────────────────┘
```

**Division of labor:** ~80% of the work is engine-side (the analysis and scheduling). The
client side is small because the delivery rail and per-channel config pattern already
exist.

## 4. Why it splits this way (the boundary)

`tests/architecture/test_engine_boundary.py` fails the build if any adapter in this repo
imports an engine package. The monitor needs `make_llm`, `SessionLocal`, DB models, and
Palace — all engine-only. Therefore:

- **Analysis + scheduling MUST live in `mypal-engine`.** We cannot revive the cut files
  here.
- **The client only does config + delivery**, talking to the engine over the two existing
  rails:
  - **Gateway WS** (`adapters/base.py`) — engine pushes `ProactiveMessage` to the adapter.
  - **HTTP API** (`client_common/engine_client.py`) — adapter reads/writes config.

## 5. Engine-side design (`mypal-engine`)

### 5.1 Scheduler
Resurrect `scheduler.py` + `heartbeat.py` as a `ChannelMonitorScheduler`:
- Loads the set of monitored channels and their cadence from the DB.
- On each tick, for each due channel, runs the monitor job.
- Per-channel cadence (e.g. hourly, every 6h, daily) and a quiet-hours window.
- Idempotency: track `last_run_at` and the last message id processed so a run only
  considers messages since the previous run.

### 5.2 Message source
The engine already ingests Discord messages (the adapter forwards them over WS for normal
chat). The monitor needs a **rolling buffer / queryable store** of recent channel messages
to summarize. Options, in order of preference:
1. If the engine already persists inbound messages (Palace / a messages table), query that
   window directly. **Confirm during implementation.**
2. Otherwise, add a lightweight ring-buffer per monitored channel populated from the same
   inbound-message hook.

### 5.3 Pre-filter (cheap, no LLM)
Run `sentiment.py` (VADER) over the window to compute a negativity/heat score. This gates
the expensive issue-scan pass: always run the digest, but only run the LLM issue scan when
heat crosses a threshold **or** every Nth run as a safety net. Keeps token cost down on
calm channels.

### 5.4 Digest pass (LLM)
Reuse `channel_summaries.py` + `topics.py`:
- Split window into older (summarized) + recent (verbatim) as before.
- Produce: top topics/themes, activity level, notable threads, optional sentiment trend
  vs. previous run (topics.py already tracks recurrence + sentiment trend).
- Output is prose suitable for a public channel.

### 5.5 Issue-scan pass (LLM) — the differentiator
A **separate prompt** whose only job is to surface problems. Returns **structured JSON**,
not prose, so the client can render/threshold it:

```json
{
  "flags": [
    {
      "severity": "high",            // low | medium | high
      "category": "conflict",        // conflict | complaint | confusion | blocker | moderation | other
      "summary": "Two members are escalating an argument about <topic>.",
      "participants": ["alice", "bob"],
      "evidence": ["<short quoted snippet>", "..."],
      "suggested_action": "A mod may want to step in."
    }
  ]
}
```

Prompt guidance: be conservative (false positives erode trust), quote rather than
paraphrase as evidence, never flag normal disagreement/banter, collapse duplicates across
runs (track recently-emitted flags to avoid re-alerting the same ongoing situation).

### 5.6 Emission
Both outputs are sent as existing `ProactiveMessage`s over the Gateway WS:
- Digest → `channel` = configured digest channel, `priority = "normal"`.
- Each flag (or a batched flag report) → `channel` = configured admin channel (or `user` =
  an admin for DM), `priority = "high"`.

`ProactiveMessage` already carries `user`, `channel`, `content`, `priority`
(`mypal_protocol/messages.py:316`). See §6 for the one optional protocol extension.

## 6. Client-side design (`mypalclara` — this repo)

### 6.1 Delivery — already works
`DiscordGatewayClient.on_proactive_message` (`gateway_client.py:783`) already DMs a user and
**falls back to posting in a channel**. A channel-targeted `ProactiveMessage` will be
delivered today with no change. Minimum viable delivery is therefore **zero client code**.

### 6.2 Optional protocol extension for nicer flag rendering
To make admin flags visually distinct (red embed, severity, participants, evidence,
optional admin ping) instead of plain text, add a structured variant rather than stuffing
JSON into `content`:

- New `MessageType.MONITOR_REPORT = "monitor_report"` in `mypal_protocol/messages.py`
  (enum at line 16; register in the `Message` union ~line 488 and the type map ~line 563).
- New model `MonitorReportMessage` carrying `kind: Literal["digest","flags"]`, target
  channel/user, and either `content: str` (digest) or a typed `flags: list[Flag]`.
- Handler `on_monitor_report` in the Discord gateway client that renders digest as plain
  text and flags as an embed via the existing `ui/embeds.py` helpers.

This is **optional** — ship on `ProactiveMessage` first, add `MonitorReportMessage` as a
polish pass. Both repos share `mypal_protocol`, so the protocol change must land in lockstep.

### 6.3 Configuration
Mirror the existing `channel_modes.py` pattern (cache + `EngineApiClient` HTTP, no engine
import). New config per guild/channel:
- `monitored: bool`, `cadence`, `quiet_hours`
- `digest_channel_id`
- `admin_channel_id` *or* `admin_user_ids` (where flags go)
- issue-scan sensitivity threshold

New `EngineApiClient` methods (HTTP, e.g. `get_monitor_config` / `set_monitor_config`),
matching the style of `get_channel_mode` / `set_channel_mode`
(`engine_client.py:66`/`:69`). The engine owns the storage.

### 6.4 Admin UX
Add slash commands under the existing `adapters/discord/ui/commands.py` (admin-gated):
- `/monitor enable` / `/monitor disable`
- `/monitor digest-channel #channel`
- `/monitor admin-channel #channel` (or `/monitor admin-dm @user`)
- `/monitor cadence <hourly|6h|daily>`
- `/monitor status` / `/monitor run-now` (manual trigger for testing)

## 7. Configuration (proposed env / defaults)

Engine-side (mirrors the old ORS/summary knobs):
- `MONITOR_ENABLED` (default false)
- `MONITOR_DEFAULT_CADENCE_MINUTES` (default 360)
- `MONITOR_SUMMARY_AGE_MINUTES` (reuse `DISCORD_SUMMARY_AGE_MINUTES`, default 30)
- `MONITOR_ISSUE_SENSITIVITY` (VADER threshold gating the LLM scan)
- `MONITOR_QUIET_HOURS` (e.g. `22-7`)

## 8. Privacy & trust considerations

- **Disclosure:** members should know a channel is monitored/summarized. Recommend the
  digest channel be public and an info notice on enable.
- **Flags are private by construction** — they go to admins only, never the digest.
- **Conservative flagging:** tune for few, high-confidence flags; banter and normal
  disagreement must not trip it. Track recent flags to avoid re-alerting ongoing
  situations.
- **Retention:** define how long raw messages / summaries are stored engine-side; prefer
  summarize-then-discard for the raw window.
- **Respect existing gating:** honor `DISCORD_ALLOWED_*` and channel `off` mode — never
  monitor a channel Clara is excluded from.

## 9. Build phases

| Phase | Repo | Deliverable |
|---|---|---|
| 0 | both | Confirm engine persists/queries recent Discord messages (§5.2) |
| 1 | mypal-engine | Resurrect scheduler + heartbeat; digest pass via channel_summaries/topics; emit digest as `ProactiveMessage` to a hardcoded channel |
| 2 | mypalclara | `EngineApiClient` monitor config + `/monitor` slash commands; per-guild targets |
| 3 | mypal-engine | VADER pre-filter + LLM issue-scan pass; emit flags (batched) to admin target |
| 4 | both | Optional `MonitorReportMessage` protocol type + embed rendering for flags |
| 5 | both | Sensitivity tuning, dedupe/cooldown, quiet hours, docs + wiki page |

Phases 1–2 already give a usable scheduled digest. Phase 3 adds the semantic flagging that
is the heart of the request.

## 10. Open questions

1. Does the engine already persist inbound Discord messages in a form the monitor can query
   over its window, or do we add a buffer? (Phase 0.)
2. Flags: one `ProactiveMessage` per flag, or one batched report per run? (Lean batched to
   avoid admin spam.)
3. Admin target: dedicated admin channel, DM to specific admins, or both configurable?
4. Should the digest include a sentiment trend line vs. the previous run (topics.py
   supports it), or stay purely topical?
5. Multi-channel: per-channel digests, or one rolled-up server digest across several
   monitored channels?

## 11. Reference: key existing code

- `mypalclara/adapters/discord/channel_modes.py` — config pattern to mirror
- `mypalclara/adapters/discord/gateway_client.py:783` — `on_proactive_message` (delivery rail)
- `mypal_protocol/messages.py:316` — `ProactiveMessage`; enum at `:16`, union `~:488`, map `~:563`
- `mypalclara/client_common/engine_client.py:66` — `get_channel_mode` / `set_channel_mode` style
- Cut prior art: `git show da1ec35^:mypalclara/gateway/channel_summaries.py` (and `scheduler.py`,
  `core/sentiment.py`, `core/memory/context/topics.py`, `services/proactive/engine.py`)
