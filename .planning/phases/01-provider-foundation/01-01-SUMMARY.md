---
phase: 01-provider-foundation
plan: 01
subsystem: gateway-core
tags: [provider, singleton, protocol, abc, infrastructure]
dependency-graph:
  requires: []
  provides: [Provider-ABC, ProviderManager-singleton, protocol-versioning]
  affects: [01-02, 01-03, 02-01]
tech-stack:
  added: []
  patterns: [singleton, abstract-base-class, protocol-versioning]
key-files:
  created:
    - gateway/providers/__init__.py
    - gateway/providers/base.py
  modified:
    - gateway/protocol.py
    - gateway/__init__.py
decisions:
  - id: D01-01-01
    decision: "Provider ABC uses running property instead of status enum"
    rationale: "Simpler for initial implementation; can extend later if needed"
  - id: D01-01-02
    decision: "Protocol version checking logs but doesn't reject mismatches"
    rationale: "Backward compatibility more important than strict enforcement"
metrics:
  duration: "3 minutes"
  completed: "2026-01-27"
---

# Phase 01 Plan 01: Provider ABC and Protocol Versioning Summary

**One-liner:** Provider ABC with lifecycle methods, ProviderManager singleton, and protocol_version field on all 15 gateway message types.

## What Was Built

### Task 1: Provider ABC and ProviderManager

Created the core provider infrastructure in `gateway/providers/`:

**`gateway/providers/base.py` (212 lines)**
- `PlatformMessage` dataclass for normalized message format
- `Provider` ABC with required interface:
  - `name` property (abstract) - Provider identifier
  - `running` property - Tracks provider state
  - `start()` async method (abstract) - Initialize and connect
  - `stop()` async method (abstract) - Cleanup and disconnect
  - `normalize_message()` (abstract) - Convert platform message to PlatformMessage
  - `send_response()` async method (abstract) - Send response with optional files
  - `format_user_id()` helper - Creates unified user IDs

**`gateway/providers/__init__.py` (313 lines)**
- `ProviderManager` singleton class with:
  - `get_instance()` class method - Returns singleton
  - `register(provider)` - Add provider to registry
  - `unregister(name)` - Remove provider
  - `get(name)` - Get provider by name
  - `start_all()` - Start all registered providers concurrently
  - `stop_all()` - Stop all providers concurrently
  - `start(name)` / `stop(name)` - Individual provider control
  - `providers` property - Dict of name -> Provider
  - Thread-safe with asyncio.Lock
- `get_provider_manager()` convenience function

### Task 2: Protocol Versioning

Updated `gateway/protocol.py` to support protocol versioning:

- Added `PROTOCOL_VERSION = "1.0.0"` constant
- Added `protocol_version` field to all 15 message types:
  - RegisterMessage, RegisteredMessage
  - PingMessage, PongMessage
  - MessageRequest, ResponseStart, ResponseChunk, ResponseEnd
  - ToolStart, ToolResult
  - CancelMessage, CancelledMessage
  - ErrorMessage, StatusMessage
  - ProactiveMessage
- Updated `parse_adapter_message()` and `parse_gateway_message()`:
  - Check and log version mismatches (warning level)
  - Still parse messages without version (backward compatible)
  - Debug log when version field missing

### Gateway Package Exports

Updated `gateway/__init__.py` to export:
- `PROTOCOL_VERSION`
- `Provider`, `ProviderManager`, `get_provider_manager`
- `PlatformMessage`

## Key Design Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| D01-01-01 | Provider ABC uses `running` property instead of status enum | Simpler initial implementation; start/stop binary state sufficient for now |
| D01-01-02 | Protocol version checking logs but doesn't reject mismatches | Backward compatibility more important than strict enforcement; allows gradual migration |

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

```
All verification passed
- Provider ABC found with required methods
- ProviderManager singleton works correctly
- PROTOCOL_VERSION = "1.0.0"
- Messages include protocol_version with default
- Backward compatible parsing (missing version accepted)
- Gateway package exports all new symbols
```

## Commits

| Hash | Message |
|------|---------|
| ee2be2c0 | feat(01-01): add Provider ABC and ProviderManager singleton |
| 97918825 | feat(01-01): add protocol versioning to all gateway messages |
| a1c9f09d | chore(01-01): export providers and protocol version from gateway package |

## Next Plan Readiness

**01-02 Prerequisites:**
- [x] Provider ABC defined - Ready for DiscordProvider implementation
- [x] ProviderManager singleton - Ready to register Discord provider
- [x] Protocol versioning - Messages ready for version negotiation

**No blockers identified.**
