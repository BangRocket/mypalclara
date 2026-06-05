# CLAUDE.md

Guidance for Claude Code working with this repository.

## Project Overview

MyPalClara is the **client repo** for Clara — the platform adapters people use to talk to Clara. **Implemented today: Discord, Teams, CLI** (plus a Pipecat voice server). Slack, Telegram, Matrix, Signal, and WhatsApp appear in `adapters/manifest.py`'s discovery list but are **planned, not built** — no code exists for them yet. The **engine** (gateway, runtime, memory/Palace, LLM, tools, MCP, sandbox, database) lives in the separate **`mypal-engine`** repo (`github.com/BangRocket/mypal-engine`).

Adapters connect to a **running engine** over WebSocket (`:18789`) and HTTP API (`:18790`). They import **no** engine internals — only:

- **`mypal_protocol`** — the shared Pydantic wire contract (vendored top-level package)
- **`mypalclara.client_common`** — client helpers, incl. `EngineApiClient` (HTTP client for the engine API), plus relocated `platform`/`toolspec`/`ids` contracts
- **`mypalclara.config.logging`** — client-retained console + Discord log handlers

This boundary is enforced by `tests/architecture/test_engine_boundary.py` (it fails if any adapter imports an engine package).

## Quick Reference

```bash
# Development
poetry install                    # Install dependencies
poetry run ruff check . && poetry run ruff format .  # Lint + format
poetry run pytest tests/          # Client test suite

# Run adapters (they connect to a RUNNING mypal-engine; start that from the mypal-engine repo)
CLARA_GATEWAY_SECRET=... poetry run python -m mypalclara.adapters.discord                  # one adapter, its own process
CLARA_GATEWAY_SECRET=... poetry run python -m mypalclara.adapters.cli.launch_adapters discord teams  # dev: launch several
CLARA_GATEWAY_SECRET=... poetry run python -m mypalclara               # default entry → adapter launcher

# Docker (client adapters → external engine)
CLARA_GATEWAY_SECRET=... docker compose --profile discord up
CLARA_GATEWAY_SECRET=... docker compose --profile teams up
```

## Versioning

CalVer: `YYYY.WW.N` (Year.Week.Build). Auto-bumped via git hook for significant commits.

**Bumps version:** `feat:`, `fix:`, `perf:`, `breaking:`
**No bump:** `chore:`, `docs:`, `style:`, `refactor:`, `test:`, `ci:`, `build:`
**Override:** `[bump]` forces bump, `[skip-version]` skips bump

```bash
git config core.hooksPath .githooks  # Enable hooks (run once)
```

## Architecture (client)

| Path | Purpose |
|------|---------|
| `mypalclara/adapters/` | Platform adapters — **discord, teams, cli** (slack/telegram/matrix/signal/whatsapp are in the manifest's discovery list but unbuilt) |
| `mypalclara/adapters/base.py` | `GatewayClient` base — the WebSocket connection to the engine |
| `mypalclara/adapters/cli/launch_adapters.py` | Dev launcher: run several adapters locally |
| `mypalclara/client_common/engine_client.py` | `EngineApiClient` — typed async HTTP client for the engine `/api/v1` surface |
| `mypalclara/client_common/{platform,toolspec,ids}.py` | Contracts vendored out of the engine |
| `mypalclara/config/logging.py` | Console + Discord log handlers (no DB handler — that's engine-side) |
| `mypalclara/services/voice/` | Voice server (Pipecat / WebRTC) |
| `mypal_protocol/` | Shared wire contract (Pydantic messages); installable as `mypal-protocol` |
| `services/{discord,base,web-ui}/` | Docker build contexts (client) |

### How adapters reach the engine

- **WebSocket** (`GatewayClient`, `adapters/base.py`): chat in/out + streaming, MCP ops, proactive/heartbeat delivery. Registers with `CLARA_GATEWAY_SECRET`; the engine returns an `adapter_token`.
- **HTTP API** (`EngineApiClient`, `client_common/engine_client.py`): everything that used to be an in-process engine call — backup, sandbox status, channel/guild config, email accounts, identity links, MCP management + Smithery OAuth, memory stats. Sends `X-Gateway-Secret`.

**Rule:** if an adapter needs engine data or services, call `EngineApiClient` (HTTP) or use the `GatewayClient` WS path — never import an engine package. The architecture test enforces this.

### Model tiers (Discord)

Message prefixes select the engine model tier per-message: `!high`/`!opus` (high), `!mid`/`!sonnet` (mid, default), `!low`/`!haiku`/`!fast` (low).

## Environment Variables (client)

### Required
- `CLARA_GATEWAY_SECRET` — shared secret; **must match the engine**.

### Engine connection
- `CLARA_GATEWAY_URL` / `CLARA_GATEWAY_HOST` / `CLARA_GATEWAY_PORT` — engine WebSocket (default `127.0.0.1:18789`)
- `CLARA_GATEWAY_API_URL` — engine HTTP API base (default `http://127.0.0.1:18790`)

### Discord
- `DISCORD_BOT_TOKEN`, `DISCORD_CLIENT_ID`
- `DISCORD_ALLOWED_SERVERS`, `DISCORD_ALLOWED_CHANNELS`, `DISCORD_ALLOWED_ROLES` (comma-separated)
- `DISCORD_MAX_MESSAGES` (default 25), `DISCORD_STOP_PHRASES`

### Teams
- `TEAMS_APP_ID`, `TEAMS_APP_PASSWORD`, `TEAMS_PORT` (default 3978)

### Logging
- `LOG_LEVEL` (default INFO)

> Engine-side config — LLM providers, embeddings, Palace/memory, database, MCP servers, sandbox, backup, heartbeat — lives in the **`mypal-engine`** repo; see its CLAUDE.md.

## Web UI

`services/web-ui/` is a Rails BFF + React frontend. Rails handles its own game logic (own PostgreSQL) and proxies other API requests to the engine's HTTP API (`CLARA_GATEWAY_API_URL`).

```bash
cd services/web-ui/backend && rails s -p 3000    # Rails API
cd services/web-ui/frontend && npm run dev       # Vite dev server (port 5173)
```

## Notes

- Poetry runs in `package-mode = false` (code runs from the repo root on `sys.path`); `mypal_protocol/` is a vendored top-level package.
- The deploy topology is two repos: run `mypal-engine` (engine + its infra: postgres/qdrant/redis/falkordb), then point these adapters at it via `CLARA_GATEWAY_*`.
