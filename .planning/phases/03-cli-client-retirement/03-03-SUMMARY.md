---
phase: 03-cli-client-retirement
plan: 03
subsystem: documentation
tags: [gateway-docs, docker-compose, claude-md, partial-complete]

# Dependency graph
requires:
  - phase: 03-02-verification
    provides: Deletion safety status (BLOCKED)
provides:
  - Updated docker-compose with gateway as primary service
  - Updated CLAUDE.md with gateway architecture documentation
  - Clear documentation of retained legacy files
affects: [04-production-hardening]

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created:
    - .planning/phases/03-cli-client-retirement/03-03-SUMMARY.md
  modified:
    - docker-compose.yml
    - CLAUDE.md

key-decisions:
  - "D03-03-01: SKIP Task 1 - discord_bot.py and email_monitor.py cannot be deleted"
  - "D03-03-02: discord-bot service marked deprecated but RETAINED"
  - "D03-03-03: Gateway documented as primary entry point with clara-cli"

patterns-established:
  - "Documentation-first approach when migration blocked"
  - "Strangler fig pattern documented for gradual migration"

# Metrics
duration: 2min
completed: 2026-01-28
---

# Phase 3 Plan 03: Documentation and Cleanup Summary

**EXECUTION STATUS: PARTIAL COMPLETE - Task 1 SKIPPED due to Phase 2 blockers**

## Performance

- **Duration:** 2 min
- **Started:** 2026-01-28T04:45:00Z
- **Completed:** 2026-01-28T04:47:08Z
- **Tasks:** 2/3 (Task 1 skipped)
- **Files modified:** 2

## Critical Deviation

**Task 1 (Delete legacy files) was SKIPPED entirely.**

The 03-02-SUMMARY.md verification identified blockers that prevent safe deletion:

### Blocker 1: discord_bot.py CANNOT be deleted
- **Reason:** DiscordProvider wraps discord_bot.py using composition (strangler fig pattern)
- **Import:** `gateway/providers/discord.py` imports `ClaraDiscordBot` from `discord_bot`
- **Resolution needed:** Refactor DiscordProvider to be standalone before deletion

### Blocker 2: email_monitor.py CANNOT be deleted
- **Reason:** Multiple external imports still exist
- **Imports:**
  - `discord_bot.py` imports EMAIL_TOOLS from email_monitor
  - `clara_core/tools.py` imports EMAIL_TOOLS and execute_email_tool from email_monitor
- **Resolution needed:** Migrate these imports to use `adapters.email` module

### Blocker 3: EmailProvider not gateway-integrated
- **Location:** EmailProvider exists in `adapters/email/provider.py` (not `gateway/providers/`)
- **Status:** Not registered in `gateway/main.py`, not started by ProviderManager
- **Resolution needed:** Integrate EmailProvider into gateway lifecycle

## Tasks Executed

### Task 2: Update Docker Compose (PARTIAL)

**Status:** COMPLETE with adjustments

**Changes made to docker-compose.yml:**
1. Updated gateway service description:
   ```yaml
   # Clara Gateway - Primary entry point for all providers (Discord, Email, CLI)
   # The gateway runs providers in-process for reduced latency and unified lifecycle.
   # Discord provider wraps discord_bot.py (strangler fig pattern)
   # Email provider wraps email_monitor.py (migration in progress)
   ```

2. Added Discord/Email env vars to gateway service:
   ```yaml
   - DISCORD_BOT_TOKEN=${DISCORD_BOT_TOKEN:-}
   - DISCORD_CLIENT_ID=${DISCORD_CLIENT_ID:-}
   - DISCORD_ALLOWED_SERVERS=${DISCORD_ALLOWED_SERVERS:-}
   - DISCORD_ALLOWED_CHANNELS=${DISCORD_ALLOWED_CHANNELS:-}
   - DISCORD_ALLOWED_ROLES=${DISCORD_ALLOWED_ROLES:-}
   - DISCORD_MAX_MESSAGES=${DISCORD_MAX_MESSAGES:-25}
   - EMAIL_MONITORING_ENABLED=${EMAIL_MONITORING_ENABLED:-false}
   - EMAIL_ENCRYPTION_KEY=${EMAIL_ENCRYPTION_KEY:-}
   - EMAIL_DEFAULT_POLL_INTERVAL=${EMAIL_DEFAULT_POLL_INTERVAL:-5}
   ```

3. Marked discord-bot service as deprecated (NOT removed):
   ```yaml
   # DEPRECATED: Use gateway service with --enable-discord instead
   # This service is retained for backward compatibility while gateway migration completes.
   # The DiscordProvider in gateway wraps this bot using the strangler fig pattern.
   # Will be removed when DiscordProvider becomes standalone.
   ```

**Commit:** d7d31942

### Task 3: Update CLAUDE.md

**Status:** COMPLETE

**Changes made to CLAUDE.md:**

1. **Added Gateway section** to Development Commands:
   ```bash
   poetry run python -m gateway                    # Start gateway with all providers
   poetry run python -m gateway --enable-discord   # Enable Discord provider
   poetry run python -m gateway --help             # Show all options
   ```

2. **Added CLI Client section:**
   ```bash
   poetry run clara-cli                            # Connect to gateway (recommended)
   poetry run python -m adapters.cli               # Alternative module invocation
   poetry run python cli_bot.py                    # Deprecated - shows migration notice
   ```

3. **Marked legacy discord_bot.py as WRAPPED:**
   ```
   - `discord_bot.py` - Discord bot (WRAPPED by DiscordProvider - do not delete)
   ```

4. **Added Provider Pattern documentation:**
   > **Provider Pattern:** Providers run inside the gateway process for reduced latency. The DiscordProvider uses composition to wrap the existing discord_bot.py code without rewriting it (strangler fig pattern). This allows gradual migration while maintaining full functionality.

5. **Updated Docker section** to show gateway as primary:
   ```bash
   # Gateway (recommended)
   docker-compose --profile gateway up                    # Run gateway with all providers

   # Legacy Discord bot (deprecated)
   docker-compose --profile discord up                    # Run Discord bot only
   ```

6. **Updated Gateway System section** - removed "(in development)" label, added clara-cli connection command

**Commit:** e742b922

## Verification Results

| Check | Result |
|-------|--------|
| `python -m gateway` imports | PASS |
| docker-compose validates | PASS |
| Gateway service description | PASS |
| discord-bot marked deprecated | PASS |
| CLAUDE.md has gateway commands | PASS |
| CLAUDE.md has clara-cli | PASS |
| Discord/Email env vars in gateway | PASS |

## Files Retained (NOT Deleted)

| File | Reason | Status |
|------|--------|--------|
| `discord_bot.py` | Wrapped by DiscordProvider (strangler fig) | RETAINED |
| `email_monitor.py` | External imports from discord_bot.py and clara_core/tools.py | RETAINED |
| `discord_monitor.py` | Web dashboard still in use | RETAINED |

## Decisions Made

1. **D03-03-01: SKIP Task 1** - Plan 03-02 verification showed BLOCKED status. Cannot safely delete discord_bot.py or email_monitor.py without completing Phase 2 migrations first.

2. **D03-03-02: Discord-bot service deprecated but RETAINED** - Mark as deprecated with comments explaining the strangler fig pattern. Service cannot be removed while DiscordProvider depends on it.

3. **D03-03-03: Gateway documented as primary entry point** - CLAUDE.md now clearly shows gateway as the recommended way to run Clara, with clara-cli as the recommended CLI client.

## Deviations from Plan

### Deviation 1: Task 1 Skipped Entirely

**Original plan:** Delete discord_bot.py, email_monitor.py, discord_monitor.py
**Actual:** All files retained

**Reason:** Plan 03-02 verification identified blockers:
- discord_bot.py is wrapped by DiscordProvider (strangler fig pattern by design)
- email_monitor.py has external imports that haven't been migrated
- discord_monitor.py is still in use for monitoring

**Rule applied:** Rule 4 (Architectural decision) - Cannot proceed with deletion without completing Phase 2 migrations. This was identified in advance and scope was adjusted before execution.

### Deviation 2: Task 2 Partial Implementation

**Original plan:** Either mark discord-bot deprecated OR remove it
**Actual:** Marked deprecated only, explicitly retained

**Reason:** DiscordProvider requires discord_bot.py to exist and function. Removing the docker service would break the gateway's Discord functionality.

## Phase 3 Completion Status

| Plan | Status | Notes |
|------|--------|-------|
| 03-01 | COMPLETE | CLI deprecation wrapper implemented |
| 03-02 | COMPLETE | Pre-deletion verification (found blockers) |
| 03-03 | PARTIAL | Documentation complete, deletions blocked |

**Phase 3 is PARTIAL COMPLETE:**
- CLI migration wrapper works correctly
- Documentation updated for gateway architecture
- Legacy files RETAINED due to incomplete Phase 2 migrations

## Next Steps Required

To complete Phase 3 fully, the following Phase 2 gaps must be addressed:

1. **Migrate email_monitor imports:**
   - Update `discord_bot.py` to use `adapters.email` instead of `email_monitor`
   - Update `clara_core/tools.py` to use `adapters.email` instead of `email_monitor`

2. **Integrate EmailProvider into gateway:**
   - Add EmailProvider to `gateway/providers/__init__.py` exports
   - Add `--enable-email` flag to `gateway/main.py`
   - Wire EmailProvider into ProviderManager lifecycle

3. **Make DiscordProvider standalone (optional):**
   - Refactor DiscordProvider to not require discord_bot.py
   - This is a larger effort and may be deferred to Phase 4

## Issues Encountered

None - plan was adjusted in advance based on 03-02 verification results.

---
*Phase: 03-cli-client-retirement*
*Completed: 2026-01-28*
