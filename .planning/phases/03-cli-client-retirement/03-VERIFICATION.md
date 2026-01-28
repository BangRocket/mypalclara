---
phase: 03-cli-client-retirement
verified: 2026-01-28T05:15:00Z
status: gaps_found
score: 5/8 success criteria verified
gaps:
  - truth: "discord_bot.py deleted from repository"
    status: failed
    reason: "DiscordProvider wraps discord_bot.py using strangler fig pattern - cannot delete"
    artifacts:
      - path: "discord_bot.py"
        issue: "File retained (174KB, 4384 lines) - DiscordProvider imports ClaraDiscordBot"
    missing:
      - "Refactor DiscordProvider to be standalone (not wrap discord_bot.py)"
      - "Move all Discord logic into gateway/providers/discord.py"
  - truth: "email_monitor.py deleted from repository"
    status: failed
    reason: "External imports prevent safe deletion"
    artifacts:
      - path: "email_monitor.py"
        issue: "File retained (29KB) - imported by discord_bot.py and clara_core/tools.py"
    missing:
      - "Migrate discord_bot.py imports to use adapters.email"
      - "Migrate clara_core/tools.py imports to use adapters.email"
      - "Remove all email_monitor.py references"
  - truth: "python -m gateway starts Discord, Email, and CLI providers"
    status: partial
    reason: "Gateway starts Discord provider only; EmailProvider not integrated"
    artifacts:
      - path: "gateway/main.py"
        issue: "No --enable-email flag, no EmailProvider import"
    missing:
      - "Add --enable-email flag to gateway/main.py"
      - "Import and start EmailProvider in gateway lifecycle"
      - "Register EmailProvider with ProviderManager"
---

# Phase 3: CLI Client & Retirement Verification Report

**Phase Goal:** Build WebSocket CLI client, delete discord_bot.py and email_monitor.py completely, establish single entry point.
**Verified:** 2026-01-28T05:15:00Z
**Status:** gaps_found
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | cli_bot.py shows migration notice and starts gateway CLI | VERIFIED | File is 35 lines, shows deprecation notice, delegates to adapters.cli.main.run() |
| 2 | poetry run python -m adapters.cli connects to gateway | VERIFIED | Module exists (147 lines main.py, 188 lines gateway_client.py), imports successfully |
| 3 | CLI history preserved at ~/.clara_cli_history | VERIFIED | HISTORY_FILE = Path.home() / ".clara_cli_history" in adapters/cli/main.py:42 |
| 4 | discord_bot.py deleted from repository | FAILED | File retained: 174,808 bytes, still required by DiscordProvider (strangler fig pattern) |
| 5 | email_monitor.py deleted from repository | FAILED | File retained: 29,104 bytes, still imported by discord_bot.py and clara_core/tools.py |
| 6 | python -m gateway starts Discord, Email, and CLI providers | PARTIAL | Gateway starts Discord only; EmailProvider exists but not integrated |
| 7 | docker-compose.yml has gateway as primary | VERIFIED | Gateway service at top, discord-bot marked DEPRECATED |
| 8 | Documentation updated | VERIFIED | CLAUDE.md has gateway commands, clara-cli script, provider pattern documentation |

**Score:** 5/8 truths verified (with 2 FAILED + 1 PARTIAL)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `cli_bot.py` | Migration wrapper (~35 lines) | VERIFIED | 35 lines, shows deprecation, delegates to adapters.cli |
| `adapters/cli/main.py` | CLI entry point | VERIFIED | 147 lines, substantive implementation |
| `adapters/cli/gateway_client.py` | Gateway WebSocket client | VERIFIED | 188 lines, 10 functions/classes |
| `pyproject.toml` | clara-cli script entry | VERIFIED | `clara-cli = "adapters.cli.main:run"` |
| `gateway/providers/discord.py` | DiscordProvider | VERIFIED | 9,257 bytes, wraps ClaraDiscordBot |
| `gateway/providers/email.py` | EmailProvider in gateway | MISSING | EmailProvider is in adapters/email/provider.py, not gateway/providers/ |
| `discord_bot.py` | DELETED | FAILED | Still exists (174KB), required by DiscordProvider |
| `email_monitor.py` | DELETED | FAILED | Still exists (29KB), has external imports |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| cli_bot.py | adapters.cli.main.run | import + call | WIRED | Migration wrapper delegates correctly |
| adapters/cli/main.py | gateway_client.py | import | WIRED | CLIGatewayClient imported and used |
| gateway/main.py | DiscordProvider | import + start | WIRED | `--enable-discord` flag works |
| gateway/main.py | EmailProvider | import + start | NOT_WIRED | No EmailProvider in gateway/main.py |
| DiscordProvider | discord_bot.py | import | WIRED | Strangler fig pattern active |
| discord_bot.py | email_monitor.py | import | WIRED | EMAIL_TOOLS still imported |
| clara_core/tools.py | email_monitor.py | import | WIRED | EMAIL_TOOLS and execute_email_tool imported |

### Requirements Coverage

| Requirement | Status | Blocking Issue |
|-------------|--------|----------------|
| CLI client connects to gateway via WebSocket | SATISFIED | - |
| python -m gateway is the only entry point needed | BLOCKED | discord_bot.py still needed by DiscordProvider |
| discord_bot.py deleted (code merged into gateway) | BLOCKED | Strangler fig pattern retains file |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| discord_bot.py | - | Retained legacy file | WARNING | Planned for deletion but blocked |
| email_monitor.py | - | Retained legacy file | WARNING | Planned for deletion but blocked |
| clara_core/tools.py | 394, 407 | Import from legacy file | WARNING | Blocks email_monitor.py deletion |

### Human Verification Required

None required - all verifiable checks are programmatic.

### Test Results

All adapter tests pass (71/71):
- `tests/adapters/test_discord_behavioral.py`: 25 tests PASSED
- `tests/adapters/test_discord_gateway.py`: 36 tests PASSED  
- `tests/adapters/test_email_provider.py`: 10 tests PASSED

## Gaps Summary

Phase 3 is **PARTIAL COMPLETE** with 3 gaps preventing full goal achievement:

### Gap 1: discord_bot.py Cannot Be Deleted (BLOCKER)

**Root Cause:** DiscordProvider uses strangler fig pattern - it wraps discord_bot.py's ClaraDiscordBot class via composition rather than reimplementing Discord logic.

**Evidence:**
```python
# gateway/providers/discord.py
from discord_bot import ClaraDiscordBot
```

**Resolution Required:**
1. Refactor DiscordProvider to be standalone (embed all Discord logic)
2. Move 4,384 lines from discord_bot.py into gateway/providers/discord.py
3. Update all imports to use DiscordProvider directly

### Gap 2: email_monitor.py Cannot Be Deleted (BLOCKER)

**Root Cause:** External imports from discord_bot.py and clara_core/tools.py prevent safe deletion.

**Evidence:**
```python
# discord_bot.py:106
from email_monitor import (EMAIL_TOOLS, ...)

# clara_core/tools.py:394
from email_monitor import EMAIL_TOOLS

# clara_core/tools.py:407
from email_monitor import execute_email_tool
```

**Resolution Required:**
1. Migrate discord_bot.py imports to use adapters.email module
2. Migrate clara_core/tools.py imports to use adapters.email module
3. Verify no other imports exist
4. Delete email_monitor.py

### Gap 3: EmailProvider Not Integrated Into Gateway (PARTIAL)

**Root Cause:** EmailProvider was created in adapters/email/provider.py (Phase 2) but never wired into gateway/main.py lifecycle.

**Evidence:**
- `gateway/main.py` has `--enable-discord` but no `--enable-email`
- No import of EmailProvider in gateway/main.py
- EmailProvider not registered with ProviderManager

**Resolution Required:**
1. Add `--enable-email` flag to gateway/main.py argument parser
2. Import EmailProvider from adapters.email
3. Start EmailProvider via ProviderManager when flag is set

## What Succeeded

1. **CLI Migration Wrapper** - cli_bot.py converted to 35-line wrapper with deprecation notice
2. **clara-cli Script Entry** - Added to pyproject.toml, works correctly
3. **CLI Gateway Client** - Substantive implementation in adapters/cli/ (335 total lines)
4. **CLI History** - Preserved at ~/.clara_cli_history
5. **Docker Compose Updated** - Gateway is primary service, discord-bot marked deprecated
6. **CLAUDE.md Documentation** - Gateway commands, clara-cli, provider pattern documented
7. **All Tests Pass** - 71 adapter tests verify behavioral parity

## What Blocked File Deletions

The strangler fig pattern chosen in Phase 1 was designed to preserve existing behavior while enabling gradual migration. However, this pattern **by design** retains the original files until the new providers are refactored to be standalone. Phase 3's deletion goal conflicts with Phase 1's architecture decision.

**Recommendation:** The deletion goal should be moved to a future phase (Phase 5 or later) after:
1. DiscordProvider is refactored to not require discord_bot.py
2. Email imports are migrated to adapters.email module
3. EmailProvider is integrated into gateway lifecycle

---

*Verified: 2026-01-28T05:15:00Z*
*Verifier: Claude (gsd-verifier)*
