# MyPalClara — Clara Experience Layer Charter

**Date:** 2026-06-05
**Status:** Approved (charter). Each roadmap item below gets its own design → plan → build cycle.
**Supersedes:** the three competing app designs — `2026-03-12-web-ui-rebuild-design` (Claude.ai clone), `2026-04-12-clara-app-design` (Jan fork), and `2026-02-21-unified-web-ui-design` (Rails BFF). They collapse into roadmap item **#2 (Unified app)**.

## Context

The gateway → `mypal-engine` extraction moved all *intelligence* — gateway, runtime, memory/Palace, LLM, tools, MCP, sandbox, database — out to the standalone **`mypal-engine`** repo (`github.com/BangRocket/mypal-engine`). What remained in `mypalclara` is a grab-bag held together by history: platform adapters, a stranded Rails + React web product (`services/web-ui`), a client SDK (`client_common`), and a vendored wire contract (`mypal_protocol`) — one repo, several unrelated purposes.

This charter gives `mypalclara` a single purpose.

## Charter (the north star)

**`mypalclara` is the Clara *experience* layer:** the set of first-party surfaces a person uses to be with Clara, all thin clients of the headless `mypal-engine` (over WebSocket `:18789` + HTTP API `:18790`).

- **Flagship:** a **unified Clara app** — one chat experience across desktop / web / mobile.
- **Secondary entry points:** the **platform adapters** (Discord / Teams / CLI) — feeding the *same* experience: shared personas, shared history, shared features. Not standalone bots.
- **Experience features around them:** voice, the persona set (Clara / Flo / Clarissa), and the Game Room.

**Owns (in-repo):** the unified app · the adapters · voice · personas · games (UI) · the shared client SDK (`client_common` / `EngineApiClient`) + wire contract (`mypal_protocol`).

**Explicitly does *not* own:**
- Anything *intelligent* — memory/Palace, LLM, tools, sandbox, DB, and **game logic** → `mypal-engine`.
- The **visual-clara avatar** — its own repo and a *peer* client of the engine. It may *consume* mypalclara's published client SDK, but is not built here.

**The "does it belong here?" test:** *Is it a first-party surface — or a feature of one — that a user directly experiences, and does it stay a thin client of the engine?* Yes → `mypalclara`. Intelligence → engine. The avatar → visual-clara.

## Target structure

Organized by *language ecosystem × surface*. This is the **destination**; the roadmap sequences how we get there from today's `mypalclara/`-package layout. It is **not** a move to make up front.

| Home | Contents | Today |
|------|----------|-------|
| **`app/`** | The unified Clara app — React/Vite frontend, Tauri for desktop/mobile. The flagship. Talks **straight to the engine** (WS + HTTP), no BFF. Includes the Game Room UI. | absorbs `services/web-ui` frontend |
| **Python surfaces** | The **adapters** (discord/teams/cli + shared `GatewayClient` base) and **voice** — kept Python, sharing the client SDK. (May stay under `mypalclara/` or get a cleaner top-level home in the reorg sub-project.) | `mypalclara/adapters`, `mypalclara/services/voice` |
| **`packages/`** | The shared **client SDK** (`EngineApiClient` + platform/toolspec/ids) and **`mypal_protocol`**, packaged so both the Python surfaces and the TS app consume them. The app needs a **TS twin** (client + types generated from the protocol): one contract, two language bindings. | `mypalclara/client_common`, `mypal_protocol/` |
| **`personas/`** | Clara / Flo / Clarissa definitions, shared by every surface. | `personalities/` |

**Retired / reconciled:**
- `services/web-ui` **Rails BFF → retired.** React frontend folds into `app/`; the app talks directly to the engine. This picks the **direct-to-engine** lineage over the Rails-BFF one.
- The **three competing app designs collapse into one** (`app/`).
- **Games:** UI → `app/`, logic → engine (which already exposes a `game` API from the Phase-1 extraction). **No Rails, no Postgres** remain in this repo.
- **visual-clara** stays its own repo (peer client; may import the published SDK).

Net: the repo becomes **Python (adapters + voice + SDK) × TypeScript (app)** only.

## Roadmap

Each item is its own brainstorm → plan → build cycle. Order follows the dependencies.

| # | Sub-project | Scope / depends on |
|---|-------------|--------------------|
| **0** | **This charter** | The north star (this doc). |
| **1** | **Shared contract, two bindings** | Publish `mypal_protocol`; add a **TS client + generated types** so the app has a typed path to the engine. Foundational and small; establishes `packages/`. Also lets visual-clara reuse it. |
| **2** | **Unified app — web MVP** | The flagship. React, direct-to-engine, **Discord-parity chat** (streaming, tools, files, model tiers) + personas + shared history. Lands in `app/`, absorbing the web-ui frontend. *Needs #1.* Large — its own deep brainstorm decides tech (Jan-fork vs assistant-ui), auth, and the conversation/branching model. |
| **3** | **Games → engine + app** | Grow the engine's `game` API into full game logic; build the Game Room UI in `app/`. *Parallelizable once #2's shell exists.* |
| **4** | **Retire `services/web-ui`** | Fold any remaining bits, delete the Rails BFF + game backend. *Needs #2 parity + #3.* |
| **5** | **Desktop / mobile via Tauri** | Wrap the web app for native. *Needs #2.* |
| **6** | **Adapters alignment + repo reorg** | Polish Discord/Teams/CLI as true secondary entry points (shared personas/history/feature set); finish relocating Python surfaces into the target layout. *Mostly independent; trails the rest.* |

## Principles

- **Thin client always.** No surface embeds intelligence; everything is a client of the engine.
- **One contract, two bindings.** `mypal_protocol` is the single source of truth; Python and TS bindings are generated/derived from it, never hand-diverged.
- **Engine owns shared state.** Personas and conversation history live engine-side and are shared across every surface — that's what makes adapters "secondary entry points to the same experience" rather than separate bots.
- **YAGNI on surfaces.** No new surface until the unified app proves the pattern. (Slack/Telegram/Matrix/Signal/WhatsApp remain unbuilt until there's demand.)

## Risks & open questions

- **The app (#2) is a large build** — the bulk of the effort lives in one sub-project; its own brainstorm must scope an MVP tightly.
- **Polyglot overhead** — Python + TS in one repo adds CI/tooling/release complexity; the reorg sub-project (#6) should standardize this.
- **Auth is unsettled** — the prior designs disagree (Clerk vs none); deferred to #2.
- **Games rewrite (#3) is non-trivial** — moving game logic fully into the engine and the UI into `app/` is more than a port.
- **TS-binding generation approach** (codegen from Pydantic vs hand-authored) — decided in #1.
