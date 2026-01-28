---
phase: 01-provider-foundation
plan: 03
subsystem: gateway
tags: [gateway, provider, integration, startup, lifecycle]

# Dependency graph
requires:
  - phase: 01-01
    provides: Provider ABC and ProviderManager singleton
  - phase: 01-02
    provides: DiscordProvider wrapping ClaraDiscordBot
provides:
  - Gateway startup initializes ProviderManager
  - --enable-discord flag for optional Discord provider
  - Graceful provider shutdown on gateway exit
  - Provider classes exported from gateway package
affects: [02-01, gateway operations, production deployment]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Optional provider registration via CLI flag"
    - "Environment variable fallback: CLARA_GATEWAY_DISCORD"
    - "Graceful shutdown: providers stop before server"

key-files:
  created: []
  modified:
    - gateway/main.py
    - gateway/__init__.py
    - gateway/__main__.py

key-decisions:
  - "Discord provider disabled by default for backward compatibility"
  - "Providers start after server ready, stop before server shutdown"
  - "CLI flag with env var fallback for deployment flexibility"

patterns-established:
  - "Provider lifecycle: register -> start_all -> stop_all"
  - "Gateway startup sequence: hooks -> scheduler -> server -> providers"

# Metrics
duration: 6min
completed: 2026-01-28
---

# Phase 01 Plan 03: Gateway Integration Summary

**Gateway startup integrates ProviderManager with optional Discord provider via --enable-discord flag**

## Performance

- **Duration:** 6 min
- **Started:** 2026-01-28T07:00:00Z
- **Completed:** 2026-01-28T07:06:00Z
- **Tasks:** 3 (including checkpoint)
- **Files modified:** 3

## Accomplishments

- Added Provider, ProviderManager, get_provider_manager, DiscordProvider exports to gateway package
- Integrated ProviderManager initialization into gateway startup
- Added --enable-discord CLI flag (default: false, env: CLARA_GATEWAY_DISCORD)
- Providers start after server is ready, stop before server shutdown
- Human-verified: all three test scenarios pass (standalone bot, gateway without Discord, gateway with Discord)

## Task Commits

Each task was committed atomically:

1. **Task 1: Export provider classes from gateway package** - `bab557a7` (feat)
2. **Task 2: Integrate ProviderManager into gateway startup** - `2d81c3a0` (feat)
3. **Bugfix: Pass enable_discord arg to main** - `dcbe1d8b` (fix)

## Files Created/Modified

- `gateway/__init__.py` - Added provider exports (Provider, ProviderManager, get_provider_manager, DiscordProvider)
- `gateway/main.py` - Added --enable-discord flag, ProviderManager init, provider start/stop in lifecycle
- `gateway/__main__.py` - Fixed to pass enable_discord argument to main()

## Decisions Made

1. **Discord disabled by default:** Backward compatible - existing gateway deployments unaffected. Use `--enable-discord` or `CLARA_GATEWAY_DISCORD=true` to enable.

2. **Lifecycle ordering:** Providers start AFTER server is ready (so server can accept connections during provider startup). Providers stop BEFORE server shutdown (graceful cleanup).

3. **Environment variable fallback:** CLI flag takes precedence, but `CLARA_GATEWAY_DISCORD=true` works for Docker/production deployments.

## Deviations from Plan

1. **gateway/__main__.py not updated:** The plan specified changes to main.py but missed updating __main__.py which calls main(). Fixed with commit `dcbe1d8b`.

## Verification Results

**Test 1: Standalone Discord bot** - PASSED
- `poetry run python discord_bot.py` works exactly as before

**Test 2: Gateway without Discord** - PASSED
- `poetry run python -m gateway` starts normally
- No Discord-related logs

**Test 3: Gateway with Discord** - PASSED
- `poetry run python -m gateway --enable-discord` starts Discord provider
- Discord bot responds to messages
- Graceful shutdown stops providers first

## Phase 1 Complete

This plan completes Phase 1 (Provider Foundation). All success criteria met:

- [x] Provider base class defines clear interface (start, stop, normalize_message, send_response)
- [x] DiscordProvider wraps discord_bot.py code without rewriting core logic
- [x] Gateway can start/stop DiscordProvider programmatically
- [x] Discord messages flow through Provider.normalize_message() to PlatformMessage
- [x] Protocol version field present in all gateway messages
- [x] No behavioral regression: Discord bot responds identically to before

## Next Phase Readiness

- DiscordProvider ready for integration with MessageProcessor pipeline
- Gateway can manage provider lifecycle programmatically
- Ready for Phase 2: Gateway Integration & Email Provider

---
*Phase: 01-provider-foundation*
*Completed: 2026-01-28*
