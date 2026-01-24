# Testing Patterns

**Analysis Date:** 2026-01-24

## Test Framework

**Runner:**
- pytest 8.0+ (configured in `pyproject.toml` as dev dependency)
- Config file: Not detected (uses default pytest.ini discovery)

**Assertion Library:**
- Python's built-in `assert` statements

**Run Commands:**
```bash
poetry run pytest                    # Run all tests
poetry run pytest -v                 # Verbose output
poetry run pytest tests/             # Run specific directory
poetry run pytest --collect-only     # List test items without running
poetry run pytest -x                 # Stop on first failure
poetry run pytest -k "pattern"       # Run tests matching pattern
```

## Test File Organization

**Location:**
- Tests are co-located in `/Users/heidornj/Code/mypalclara/tests/` directory (separate from source)
- Tests directory currently contains only `__pycache__` - no active test files present
- Expected pattern for new tests: `tests/test_<module_name>.py`

**Naming:**
- Test files: `test_*.py` or `*_test.py` prefix/suffix
- Test functions: `test_<functionality>()` (e.g., `test_validate_tool_args()`)
- Test classes: `Test<Component>` (e.g., `TestToolRegistry`)

**Current State:**
- **No active test coverage** - The codebase is not currently tested via pytest
- `tests/` directory exists but contains no test files
- Only cached pytest artifacts (`.pytest_cache/`, `__pycache__/`) present
- This is a gap that should be addressed during quality improvements

## Test Structure

**Recommended Pattern (when tests are added):**
```python
import pytest
from unittest.mock import Mock, patch, AsyncMock

from clara_core.tools import ToolRegistry, ToolDef, ToolContext


class TestToolRegistry:
    """Test suite for ToolRegistry singleton."""

    def setup_method(self):
        """Set up test fixtures before each test."""
        ToolRegistry.reset()
        self.registry = ToolRegistry.get_instance()

    def teardown_method(self):
        """Clean up after each test."""
        ToolRegistry.reset()

    def test_get_instance_returns_singleton(self):
        """ToolRegistry.get_instance() returns same instance."""
        registry1 = ToolRegistry.get_instance()
        registry2 = ToolRegistry.get_instance()
        assert registry1 is registry2

    def test_register_tool(self):
        """register_tool() adds tool to registry."""
        tool = self._make_tool("test_tool")
        self.registry.register(tool)
        assert self.registry.get("test_tool") is tool

    def _make_tool(self, name: str) -> ToolDef:
        """Helper to create test tool."""
        async def handler(args, context):
            return "result"
        return ToolDef(
            name=name,
            description="Test tool",
            parameters={},
            handler=handler,
        )


@pytest.fixture
def tool_registry():
    """Fixture providing fresh registry for each test."""
    ToolRegistry.reset()
    yield ToolRegistry.get_instance()
    ToolRegistry.reset()


def test_validate_tool_args_with_fixture(tool_registry):
    """Example test using fixture."""
    args = {"param": "value"}
    params = {"properties": {"param": {"type": "string"}}}
    validated, warnings = validate_tool_args("test", args, params)
    assert validated == args
    assert warnings == []
```

**Patterns:**
- Setup/teardown methods for per-test initialization (`setup_method`, `teardown_method`)
- Class-based tests for component suites (e.g., `TestToolRegistry`)
- Fixtures for shared resources (decorators with `@pytest.fixture`)
- Singletons reset between tests to prevent state leakage

## Mocking

**Framework:** `unittest.mock` (Python standard library)

**Patterns:**
```python
from unittest.mock import Mock, MagicMock, patch, AsyncMock, call

# Mocking dependencies
@patch("clara_core.llm._get_openrouter_client")
def test_llm_with_mocked_client(mock_client):
    """Mock external LLM client."""
    mock_client.return_value = Mock(
        chat=Mock(
            completions=Mock(
                create=Mock(return_value=Mock(choices=[Mock(message=Mock(content="response"))]))
            )
        )
    )
    result = make_llm(tier="mid")
    assert result is not None
    mock_client.assert_called_once()

# Mocking async functions
@pytest.mark.asyncio
async def test_async_tool_execution():
    """Test async tool with mocked handler."""
    mock_handler = AsyncMock(return_value="tool_result")
    tool = ToolDef(
        name="test",
        description="Test",
        parameters={},
        handler=mock_handler,
    )
    context = ToolContext(user_id="test_user")
    result = await tool.handler({}, context)
    assert result == "tool_result"
    mock_handler.assert_called_once()

# Verifying calls
mock_obj.assert_called_once()
mock_obj.assert_called_once_with(arg1, arg2)
mock_obj.assert_called_with(arg1, arg2)
mock_obj.assert_not_called()
assert mock_obj.call_count == 2
assert call(arg1, arg2) in mock_obj.call_args_list
```

**What to Mock:**
- External API clients (LLM providers, Discord API)
- Database sessions/connections
- File system operations
- Long-running operations (for speed)
- Non-deterministic functions (random, timestamps)

**What NOT to Mock:**
- Core business logic (memory management, tool execution)
- Data validation functions
- Utility functions
- Pure functions (deterministic, no side effects)

## Fixtures and Factories

**Test Data:**

Currently no fixtures are defined. Recommended patterns for new tests:

```python
import pytest
from db.models import Session, Message

@pytest.fixture
def db_session():
    """Fixture providing in-memory test database."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from db.models import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    session.close()
    engine.dispose()

@pytest.fixture
def sample_session(db_session):
    """Fixture providing pre-created test session."""
    session = Session(
        id="test-session-1",
        project_id="test-project",
        user_id="test-user",
        title="Test Session",
    )
    db_session.add(session)
    db_session.commit()
    return session

@pytest.fixture
def sample_message(db_session, sample_session):
    """Fixture providing test message."""
    msg = Message(
        session_id=sample_session.id,
        user_id="test-user",
        role="user",
        content="Hello Clara",
    )
    db_session.add(msg)
    db_session.commit()
    return msg

def test_retrieve_messages(db_session, sample_session, sample_message):
    """Test retrieving messages from session."""
    messages = db_session.query(Message).filter(
        Message.session_id == sample_session.id
    ).all()
    assert len(messages) == 1
    assert messages[0].content == "Hello Clara"
```

**Location:**
- Fixtures should live in `tests/conftest.py` for sharing across test files
- Module-specific fixtures can live in individual test files
- Test data factories could be in `tests/factories.py`

## Coverage

**Requirements:** Not enforced (no coverage threshold configured)

**View Coverage (when tests exist):**
```bash
poetry run pytest --cov=clara_core --cov=db --cov-report=html
# Opens htmlcov/index.html in browser
```

**Recommended Coverage Targets:**
- Critical paths (memory management, tool execution): 80%+
- Utility functions: 70%+
- Integrations (Discord, LLM APIs): 40%+ (harder to test with mocks)
- Overall target: 60%+ for quality assurance

## Test Types

**Unit Tests:**
- Scope: Single function or class method
- Approach: Isolate with mocks, test behavior not implementation
- Example: Test `validate_tool_args()` with various input types
- Location: `tests/test_<module>.py`

**Integration Tests:**
- Scope: Multiple components working together
- Approach: Use real or in-memory dependencies (no mocks)
- Example: Test ToolRegistry registering and executing a tool
- Location: `tests/integration/test_<feature>.py`
- Marked with `@pytest.mark.integration` to run separately

**E2E Tests:**
- Framework: Not currently set up (would require Discord test server)
- Approach: Full message flow from Discord to LLM and back
- Would require: Test Discord server, API mocking or staging env
- Not prioritized - focus on unit and integration tests

## Common Patterns

**Async Testing:**
```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_async_operation():
    """Test async function."""
    result = await some_async_function()
    assert result == expected_value

@pytest.mark.asyncio
async def test_async_with_mock():
    """Test async function with mocked dependency."""
    with patch("module.dependency", new_callable=AsyncMock) as mock_dep:
        mock_dep.return_value = "mocked_result"
        result = await some_async_function()
        assert result == "mocked_result"
```

**Error Testing:**
```python
import pytest

def test_raises_on_invalid_input():
    """Test function raises expected exception."""
    with pytest.raises(ValueError, match="Invalid input"):
        function_that_validates("bad_input")

def test_handles_error_gracefully():
    """Test error handling behavior."""
    result = function_with_error_handling("bad_input")
    assert result is None  # or some error state

def test_logs_error():
    """Test that errors are logged."""
    with patch("module.logger") as mock_logger:
        function_that_logs_errors("bad_input")
        mock_logger.error.assert_called()
```

**Database Testing:**
```python
def test_create_session(db_session):
    """Test creating a database session."""
    session = Session(
        id="test-1",
        project_id="proj-1",
        user_id="user-1",
    )
    db_session.add(session)
    db_session.commit()

    retrieved = db_session.query(Session).filter_by(id="test-1").first()
    assert retrieved is not None
    assert retrieved.user_id == "user-1"

def test_session_relationships(db_session, sample_session, sample_message):
    """Test ORM relationships."""
    session = db_session.query(Session).get(sample_session.id)
    assert len(session.messages) == 1
    assert session.messages[0].content == sample_message.content
```

## Testing Gaps and Recommendations

**Current State:**
- No active test coverage
- Test infrastructure (pytest) is configured but unused
- No fixtures or test utilities defined

**High-Priority Test Areas (when implementing):**
1. **Tool execution pipeline** (`tools/_registry.py`, `validate_tool_args()`)
   - Parameter validation and coercion
   - Tool registration and lookup
   - Error handling during execution

2. **Memory management** (`clara_core/memory.py`)
   - Session creation and retrieval
   - Memory context building
   - Message history formatting

3. **LLM backends** (`clara_core/llm.py`)
   - Provider client initialization
   - Model tier selection
   - Streaming response handling

4. **Database models** (`db/models.py`)
   - Model creation and persistence
   - Relationships and foreign keys
   - Cascade operations

5. **Error handling** (all modules)
   - Recovery from API failures
   - Fallback behaviors
   - Logging of errors

---

*Testing analysis: 2026-01-24*
