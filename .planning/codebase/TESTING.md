# Testing Patterns

**Analysis Date:** 2026-01-27

## Test Framework

**Runner:**
- `pytest` 8.0+ (configured in `pyproject.toml`)
- Configuration: `pyproject.toml [tool.pytest.ini_options]` (lines 112-116)

**Async Support:**
- `pytest-asyncio` 0.24+ for async test functions
- Asyncio mode: `asyncio_mode = "auto"` (auto-detects and runs async fixtures/tests)
- Fixture scope: `asyncio_default_fixture_loop_scope = "function"` (new loop per test)

**Assertion Library:**
- Standard `assert` statements
- No custom assertion helper library

**Run Commands:**
```bash
pytest                 # Run all tests
pytest tests/          # Run specific directory
pytest -v              # Verbose output (show each test)
pytest -s              # Show print statements (don't capture)
pytest -k "pattern"    # Run tests matching pattern
pytest --lf            # Run last failed
pytest -x              # Stop on first failure
```

## Test File Organization

**Location:**
- Co-located with source: Tests in `tests/` directory mirroring source structure
- Gateway tests: `tests/gateway/test_*.py` for modules in `gateway/`
- Pattern: `tests/` at project root, subdirectories match `src/` structure

**Naming:**
- Test modules: `test_*.py` (e.g., `test_events.py`, `test_scheduler.py`, `test_hooks.py`)
- Test classes: `Test*` (e.g., `TestEvent`, `TestEventEmitter`, `TestScheduler`)
- Test functions: `test_*` (e.g., `test_creation`, `test_handler`, `test_timeout`)
- Fixture functions: `fixture_name` without `test_` prefix

**Structure:**
```
tests/
├── __init__.py
├── gateway/
│   ├── __init__.py
│   ├── test_events.py       # Tests for gateway/events.py
│   ├── test_scheduler.py    # Tests for gateway/scheduler.py
│   └── test_hooks.py        # Tests for gateway/hooks.py
```

## Test Structure

**Suite Organization:**

```python
"""Tests for gateway event system."""

import asyncio
from datetime import datetime

import pytest

from gateway.events import Event, EventEmitter, EventType


@pytest.fixture
def emitter():
    """Create a fresh event emitter."""
    return EventEmitter()


@pytest.fixture(autouse=True)
def reset_global():
    """Reset global emitter between tests."""
    yield
    reset_event_emitter()


class TestEvent:
    """Tests for Event dataclass."""

    def test_event_creation(self):
        event = Event(type=EventType.GATEWAY_STARTUP)
        assert event.type == EventType.GATEWAY_STARTUP
        assert isinstance(event.timestamp, datetime)
        assert event.data == {}
```

**Patterns:**

1. **Module docstring:** Describes what module is being tested
2. **Imports:** Organized (standard lib, third-party, local)
3. **Fixtures:** Define fresh instances and cleanup with `yield`
4. **Reset fixture:** `autouse=True` for global state cleanup between tests
5. **Test classes:** Group related tests with `Test*` class names
6. **Individual tests:** Methods starting with `test_` describing specific behavior

## Fixtures and Setup/Teardown

**Fixtures Pattern:**

```python
@pytest.fixture
def emitter():
    """Create a fresh event emitter."""
    return EventEmitter()


@pytest.fixture(autouse=True)
def reset_global():
    """Reset global emitter between tests."""
    yield  # Tests run here
    reset_event_emitter()  # Cleanup after


@pytest.fixture
def manager(emitter):
    """Create a fresh hook manager."""
    return HookManager(emitter=emitter)
```

**Key characteristics:**
- Fixtures are functions decorated with `@pytest.fixture`
- Descriptive docstrings explain what they create
- `autouse=True` for fixtures that should run for every test (global cleanup)
- `yield` for setup/teardown: setup code runs, test runs, teardown after `yield`
- Dependency injection: fixtures can depend on other fixtures by parameter name
- Fresh instances per test: Each test gets its own emitter/manager/etc.

**Cleanup strategy:**
- Global singleton reset functions: `reset_event_emitter()`, `reset_scheduler()`, `reset_hook_manager()`
- Called in `autouse=True` fixtures after `yield` for guaranteed cleanup
- Prevents test pollution and cross-test dependencies

## Mocking

**Framework:** No external mocking library detected; uses Python builtins and manual mocks

**Patterns:**

1. **Direct instantiation:** Create real instances for testing (lightweight objects)
   ```python
   def test_event_creation(self):
       event = Event(type=EventType.GATEWAY_STARTUP)
       assert event.type == EventType.GATEWAY_STARTUP
   ```

2. **Closure-based fake handlers:** Define test handlers inline
   ```python
   async def test_multiple_handlers(self, emitter):
       results = []

       async def handler1(event: Event):
           results.append("handler1")

       async def handler2(event: Event):
           results.append("handler2")

       emitter.on(EventType.GATEWAY_STARTUP, handler1)
       emitter.on(EventType.GATEWAY_STARTUP, handler2)
       await emitter.emit(Event(type=EventType.GATEWAY_STARTUP))
       assert "handler1" in results
   ```

3. **Test double data structures:** Create minimal fake objects
   ```python
   def test_load_from_file(self, scheduler):
       with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
           f.write("""
tasks:
  - name: test-task
    type: interval
    interval: 3600
    command: echo loaded
""")
           count = scheduler.load_from_file(f.name)
           assert count == 1
   ```

**What to Mock:**
- External APIs: File systems (use `tempfile`), network calls (when present, would mock HTTP)
- Long-running operations: Replace with shortened versions (e.g., `interval=0.1` instead of 3600)
- Side effects: Replace with in-memory lists/dicts to capture behavior

**What NOT to Mock:**
- Core business logic: Test real event emitters, schedulers, hook managers
- Data structures: Test with real Event, ScheduledTask, Hook objects
- Configuration: Use real config values (make them small for tests)

## Async Testing

**Pattern:**
```python
@pytest.mark.asyncio
async def test_interval_task_execution(self, scheduler):
    task = ScheduledTask(
        name="quick-task",
        type=TaskType.INTERVAL,
        interval=0.1,  # Very short interval for testing
        command="echo executed",
        timeout=5.0,
    )
    scheduler.add_task(task)

    await scheduler.start()
    await asyncio.sleep(0.5)  # Wait for execution
    await scheduler.stop()

    results = scheduler.get_results()
    assert len(results) >= 1
```

**Key points:**
- Mark async tests with `@pytest.mark.asyncio`
- Use `async def` for test function
- `await` all async calls
- Pytest-asyncio auto-detects and runs with proper event loop
- Use `asyncio.sleep()` for timing tests (not `time.sleep()`)

## Error and Exception Testing

**Pattern:**
```python
def test_invalid_expression(self):
    with pytest.raises(ValueError):
        CronParser.parse("* * *")  # Too few fields
```

**Key points:**
- Use `pytest.raises(ExceptionType)` context manager
- Test that specific exceptions are raised for invalid input
- Verify error messages when important (optional but recommended)

## Fixtures and Test Data

**Factory pattern:**
```python
def test_load_from_file(self, scheduler):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("""
tasks:
  - name: test-task
    type: interval
    interval: 3600
    command: echo loaded
    description: Test task from file
""")
        f.flush()
        count = scheduler.load_from_file(f.name)
```

**Location:**
- Fixtures in same test file with `@pytest.fixture` decorator
- Test data (YAML, JSON) created inline with `tempfile`
- No separate fixtures directory (tests are self-contained)

## Coverage

**Requirements:** Not enforced by CI (no minimum coverage configured)

**View Coverage:**
```bash
pytest --cov=gateway tests/gateway/
pytest --cov=clara_core tests/
```

**Generate HTML Report:**
```bash
pytest --cov=gateway --cov-report=html tests/gateway/
# Opens htmlcov/index.html in browser
```

## Test Types and Scope

**Unit Tests:**
- Scope: Single class or function in isolation
- Examples: `test_event_creation()`, `test_cron_parser()`, `test_hook_dataclass()`
- Approach: Direct instantiation, no external dependencies, fast execution
- Assertions: Verify state changes, return values, method calls
- Location: `tests/gateway/test_*.py` for core gateway tests

**Integration Tests:**
- Scope: Multiple components working together
- Examples: `test_handler_priority()`, `test_python_hook_execution()`, `test_interval_task_execution()`
- Approach: Real event emitters, schedulers, hooks; short timeouts for speed
- Assertions: Verify end-to-end behavior (events processed, tasks executed, handlers fired)
- Location: Same files, mixed with unit tests (via `@pytest.mark.asyncio` for async integration)

**E2E Tests:**
- Not present in current test suite
- Would test full workflows across multiple services (if added)
- Would require running services or mock infrastructure

## Common Testing Patterns in Codebase

**Handler Priority Testing:**
```python
@pytest.mark.asyncio
async def test_handler_priority(self, emitter):
    results = []

    async def low_priority(event: Event):
        results.append("low")

    async def high_priority(event: Event):
        results.append("high")

    emitter.on(EventType.GATEWAY_STARTUP, low_priority, priority=0)
    emitter.on(EventType.GATEWAY_STARTUP, high_priority, priority=10)

    await emitter.emit(Event(type=EventType.GATEWAY_STARTUP))

    # High priority should run first
    assert results[0] == "high"
    assert results[1] == "low"
```

**Timeout Testing:**
```python
@pytest.mark.asyncio
async def test_task_timeout(self, scheduler):
    task = ScheduledTask(
        name="slow-task",
        type=TaskType.ONE_SHOT,
        delay=0,
        command="sleep 10",
        timeout=0.1,  # Very short timeout
    )
    scheduler.add_task(task)

    await scheduler.start()
    await asyncio.sleep(0.5)
    await scheduler.stop()

    results = scheduler.get_results()
    assert len(results) >= 1
    assert results[0].success is False
    assert "Timeout" in results[0].error
```

**Environment Variable Testing:**
```python
@pytest.mark.asyncio
async def test_environment_variables(self, manager, emitter):
    hook = Hook(
        name="env-test",
        event=EventType.SESSION_START,
        command="echo USER:$CLARA_USER_ID CHANNEL:$CLARA_CHANNEL_ID",
        timeout=5.0,
    )
    manager.register(hook)

    await emitter.emit(
        Event(
            type=EventType.SESSION_START,
            user_id="test-user-123",
            channel_id="test-channel-456",
        )
    )
    await asyncio.sleep(0.2)

    results = manager.get_results()
    assert len(results) >= 1
    assert "USER:test-user-123" in results[0].output
    assert "CHANNEL:test-channel-456" in results[0].output
```

**Wildcard/Catch-all Handler Testing:**
```python
@pytest.mark.asyncio
async def test_wildcard_handler(self, emitter):
    received = []

    async def handler(event: Event):
        received.append(event.type)

    emitter.on("*", handler)

    await emitter.emit(Event(type=EventType.GATEWAY_STARTUP))
    await emitter.emit(Event(type=EventType.MESSAGE_RECEIVED))

    assert len(received) == 2
    assert EventType.GATEWAY_STARTUP in received
    assert EventType.MESSAGE_RECEIVED in received
```

## Test Statistics

**Current Coverage:**
- Total test files: 3 (`test_events.py`, `test_scheduler.py`, `test_hooks.py`)
- Total test cases: ~60+ individual test methods
- Focused on: Gateway system (events, scheduling, hooks)
- Minimal coverage for: Core platform modules (discord_bot, memory, llm backends)

**Gap Analysis:**
- No tests for discord_bot.py (main entry point)
- No tests for memory_manager.py (core orchestration)
- No tests for llm.py (LLM backend abstraction)
- No tests for tools.py (tool registry)
- Gateway system well-tested (high confidence in event/scheduler/hook reliability)

---

*Testing analysis: 2026-01-27*
