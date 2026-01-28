---
status: testing
phase: 01-provider-foundation
source: [01-01-SUMMARY.md, 01-02-SUMMARY.md, 01-03-SUMMARY.md]
started: 2026-01-28T07:10:00Z
updated: 2026-01-28T07:10:00Z
---

## Current Test

number: 1
name: Gateway starts without Discord (default)
expected: |
  Run `poetry run python -m gateway`
  - Gateway starts normally with "Gateway ready" message
  - No Discord-related logs appear
  - Ctrl+C stops cleanly
awaiting: user response

## Tests

### 1. Gateway starts without Discord (default)
expected: Run `poetry run python -m gateway` - starts normally without Discord logs
result: [pending]

### 2. Gateway starts with Discord provider
expected: Run `poetry run python -m gateway --enable-discord` - Discord provider registers, bot connects, responds to messages
result: [pending]

### 3. Standalone Discord bot unchanged
expected: Run `poetry run python discord_bot.py` - works exactly as before consolidation
result: [pending]

### 4. Graceful shutdown with providers
expected: When running with --enable-discord, Ctrl+C shows "Stopping providers..." then "All providers stopped" before exit
result: [pending]

### 5. Environment variable works
expected: Set `CLARA_GATEWAY_DISCORD=true` and run `poetry run python -m gateway` - Discord provider starts without --enable-discord flag
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0

## Gaps

[none yet]
