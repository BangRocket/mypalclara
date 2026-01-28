---
phase: 03-cli-client-retirement
plan: 04
subsystem: email
tags: [email, tools, migration, adapters]

# Dependency graph
requires:
  - phase: 02-gateway-integration-email
    provides: adapters.email.monitor with EmailMonitor class
provides:
  - EMAIL_TOOLS list exported from adapters.email
  - handle_email_tool and execute_email_tool functions
  - email_check_loop for Discord bot background polling
  - email_monitor.py external imports removed (can now be deleted)
affects: [03-05-PLAN, phase-4]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Email tools in adapters.email.tools module"
    - "Re-export pattern in adapters.email.__init__.py"

key-files:
  created:
    - adapters/email/tools.py
  modified:
    - adapters/email/__init__.py
    - discord_bot.py
    - clara_core/tools.py

key-decisions:
  - "D03-04-01: Copy full tool definitions from email_monitor.py rather than importing"
  - "D03-04-02: Keep execute_email_tool as alias for backward compatibility"
  - "D03-04-03: Move LLM email evaluation functions to tools.py alongside handlers"

patterns-established:
  - "Email tools self-contained in adapters/email/tools.py"
  - "Import from adapters.email instead of legacy email_monitor"

# Metrics
duration: 2min
completed: 2026-01-28
---

# Phase 3 Plan 4: Email Import Migration Summary

**Email tools migrated from email_monitor.py to adapters.email module - external imports removed, email_monitor.py now deletable**

## Performance

- **Duration:** 2 min (152 seconds)
- **Started:** 2026-01-28T15:12:37Z
- **Completed:** 2026-01-28T15:15:09Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Created adapters/email/tools.py with EMAIL_TOOLS, handlers, and email_check_loop
- Updated adapters/email/__init__.py to export all email tool functions
- Migrated imports in discord_bot.py and clara_core/tools.py from email_monitor to adapters.email
- email_monitor.py now has zero external imports and can be safely deleted

## Task Commits

Each task was committed atomically:

1. **Task 1: Create adapters/email/tools.py** - `862367fe` (feat)
2. **Task 2: Update adapters/email/__init__.py exports** - `b96c1263` (feat)
3. **Task 3: Migrate imports in discord_bot.py and clara_core/tools.py** - `48831da8` (refactor)

## Files Created/Modified
- `adapters/email/tools.py` - Email tool definitions, handlers, check loop, LLM evaluation
- `adapters/email/__init__.py` - Added exports for EMAIL_TOOLS, handle_email_tool, execute_email_tool, email_check_loop
- `discord_bot.py` - Changed import from email_monitor to adapters.email
- `clara_core/tools.py` - Changed imports from email_monitor to adapters.email

## Decisions Made

- **D03-04-01:** Copied full tool definitions rather than wrapping email_monitor - ensures complete independence
- **D03-04-02:** Keep execute_email_tool as alias for handle_email_tool - backward compatibility for clara_core/tools.py
- **D03-04-03:** Moved evaluate_and_respond and send_email_response to tools.py - keeps all email tool logic together

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all verifications passed on first attempt.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Gap 2 from 03-VERIFICATION.md is now CLOSED
- email_monitor.py can be deleted in 03-05-PLAN.md
- All email functionality now available via adapters.email module

---
*Phase: 03-cli-client-retirement*
*Completed: 2026-01-28*
