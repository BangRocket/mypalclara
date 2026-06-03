# Client Trim — Coupling Inventory & Decomposition (Phase 2c)

> Precondition to trimming `mypalclara` down to a client-only repo. The engine is already
> extracted (`mypal-engine`). This doc inventories how the **client still reaches into engine
> internals** and decomposes the rewire into ordered sub-plans. **No code changes yet** —
> this is the "plan first" artifact for the trim.

## Why this exists

After the engine repo split, `mypalclara` is still the full monorepo (engine + client). Naively
deleting the engine folders breaks the client, because the client does not merely *coexist* with
the engine — it **imports engine internals in-process** at ~30 call sites, including **direct
database access**. The core design rule is "engine owns the DB exclusively; clients use its API."
The client violates that today. Every violation must be converted to an API call (or the code
moved) **before** any engine folder can be removed.

## Coupling inventory (client = `mypalclara/adapters`, `mypalclara/web`, `mypalclara/services/voice`)

### Category A — Shared/misplaced utilities (MOVE to client or shared; no API needed)

| Import | Sites | Disposition |
|---|---|---|
| `mypalclara.config.logging` → `get_logger`, `init_logging` | 22 files | Client gets its own small logging module (or a shared util). Pure utility, no engine logic. |
| `mypalclara.core.platform` → `PlatformAdapter`, `PlatformContext`, `PlatformMessage` | 2 files | Adapter base contracts — belong client-side (or shared). Move next to `adapters/base.py`. |
| `mypalclara.tools._base` → `ToolContext`, `ToolDef` | 1 file | Tool-definition types. Move or vendor client-side. |
| `mypal_protocol` (via the `mypalclara.gateway.protocol` shim) | 1 gateway import | Already a standalone package. Client switches to a **direct dependency** on published `mypal-protocol`. |

### Category B — Direct DB access (VIOLATES "engine owns DB" → must become API)

| Import | Sites | API today |
|---|---|---|
| `mypalclara.db.SessionLocal` | `adapters/cli/commands.py`, `adapters/discord/channel_modes.py`, `adapters/discord/ui/commands.py` | n/a (direct DB) |
| `db.models`: `PlatformLink`, `CanonicalUser` | several | **Partial** — `users` router exposes `/me`, `/me/links` |
| `db.models`: `ChannelConfig` + `db.channel_config.set_channel_mode` | channel modes | **None** — must build |
| `db.models`: `GuildConfig` | discord | **None** — must build |
| `db.models`: `EmailAccount` | discord | **None** — must build |
| `db.models`: `gen_uuid` | 1 | Trivial util — vendor client-side |

### Category C — In-process engine services (must become API)

| Import | Sites | API today |
|---|---|---|
| `core.memory.ClaraMemory` | `adapters/discord/ui/commands.py` | **Partial** — `memories` router exists; verify it covers the call |
| `core.mcp.get_mcp_manager` (+ `mcp.oauth`, `mcp.installer`, `mcp.models`) | 13+ | **None** — biggest single chunk; no MCP endpoints exist |
| `core.services.backup.get_backup_service` | 3 | **None** — must build a backup-trigger endpoint |
| `sandbox.manager.get_sandbox_manager` | 1 | **None** — must build a sandbox-trigger endpoint |

## Engine API gap analysis

**Already exist** (`mypalclara/gateway/api/`): `chat`, `sessions`, `memories`, `graph`,
`intentions`, `users` (partial), `admin` (users approve/suspend only), `game`.

**Must be BUILT before the client can drop in-process calls:** MCP management, channel-config,
guild-config, email-accounts, backup-trigger, sandbox-trigger. This is **engine-side feature
work**, not client deletion — it is the bulk of the effort.

## Decomposition (ordered sub-plans)

1. **Shared foundation** (Category A) — give the client its own `logging`, the platform/tool
   contract types, and `gen_uuid`; publish `mypal-protocol` and make the client depend on it.
   *Low risk, no engine API changes, unblocks everything. Client stays runnable throughout.*
2. **Engine API gap-fill** (Category B/C endpoints) — build the missing endpoints: MCP mgmt,
   channel/guild config, email accounts, backup, sandbox. *Engine-side; must land before rewire.*
3. **Client rewire** (Category B + C call sites) — replace each `SessionLocal` / `ClaraMemory` /
   MCP / backup / sandbox in-process call with an engine **API-client** call. *One file at a time;
   client boots after each.*
4. **Cut** (mechanical) — delete engine paths from `mypalclara`, switch `pyproject` to the
   published `mypal-protocol`, update Docker/compose/CI, add a boundary test asserting the client
   imports **no** engine internals, verify the client boots and connects to a running engine.

**Sequencing:** 4 needs 3; 3 needs 2; 1 is independent and safe to do first.

## Decisions (resolved 2026-06-03)

1. **Where does the engine API gap-fill (step 2) happen? → `mypal-engine` is canonical.** All
   engine-side work (the 6 new endpoint groups) is built **directly in the `mypal-engine` repo**
   from now on, and local dev runs the engine from there. `mypalclara`'s in-tree engine code is
   treated as dead code awaiting deletion (no longer kept live). This removes the "two copies
   diverge" tax — we build forward in the engine repo and only ever *delete* from `mypalclara`.
2. **Shared code distribution → vendor small copies** into the client (logging, `gen_uuid`,
   platform/tool contracts). No third published `mypal-common` lib for now. *(default; revisit if it
   grows)*
3. **`mypal-protocol` distribution → git-tag dependency** to start (point `mypalclara` at a tagged
   commit / subdir of `mypal-engine`); PyPI publish later. *(default; revisit at the cut)*

### Revised per-repo home for each sub-plan

| Sub-plan | Repo it happens in |
|---|---|
| 1. Shared foundation | `mypalclara` (client vendors utils) + publish `mypal-protocol` from `mypal-engine` |
| 2. Engine API gap-fill | **`mypal-engine`** (canonical) |
| 3. Client rewire | `mypalclara`, tested against a locally-running `mypal-engine` |
| 4. Cut | `mypalclara` (delete engine paths, finalize deps) |

## Definition of done

`mypalclara` contains only client code (`adapters/`, `web/`, `services/voice/`, client config);
imports `mypal_protocol` + an engine API client only; boundary test green; client boots and
connects to a running `mypal-engine` over WS + HTTP with no in-process engine imports.
