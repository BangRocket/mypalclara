# Client Trim — Sub-plan 1: Shared Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or
> subagent-driven-development) to implement this plan task-by-task. Steps use checkbox (`- [ ]`).

**Goal:** Relocate the three small shared utilities the client imports out of soon-to-be-deleted
engine packages (`core`, `tools`, `db`) into a client-retained `mypalclara/client_common/` package,
so the client no longer depends on engine internals for them — without breaking the monorepo.

**Architecture:** Copy (not move) `PlatformMessage`/`PlatformContext`/`PlatformAdapter`,
`ToolContext`/`ToolDef`, and `gen_uuid` into `mypalclara/client_common/`. Repoint the 4 client
import sites. Engine keeps its own copies (deleted later at the cut). Logging stays in
`mypalclara/config/logging.py` (client-retained; trimmed at the cut). Protocol is already on
`mypal_protocol` directly — untouched here. A new architecture test locks the boundary.

**Tech Stack:** Python 3.12, pytest (`asyncio_mode = auto`), ruff (`E/F/I`), AST scanning.

**Scope guard:** This sub-plan touches ONLY the shared utilities. The `db.models` imports of
`PlatformLink`/`CanonicalUser`/`ChannelConfig`/etc. and `core.memory`/`core.mcp`/`backup`/`sandbox`
calls are Sub-plans 2–3 — do NOT touch them here.

---

## File Structure

- Create: `mypalclara/client_common/__init__.py` — package marker + re-exports
- Create: `mypalclara/client_common/platform.py` — adapter contracts (copied from `core/platform.py`)
- Create: `mypalclara/client_common/toolspec.py` — `ToolContext`/`ToolDef` (copied, engine-free)
- Create: `mypalclara/client_common/ids.py` — `gen_uuid`
- Modify: `tests/architecture/test_engine_boundary.py` — add `test_client_does_not_import_relocated_shared_code`
- Modify: `mypalclara/adapters/cli/adapter.py:18` — repoint platform import
- Modify: `mypalclara/adapters/discord/adapter.py:18` — repoint platform import
- Modify: `mypalclara/adapters/cli/tools.py:23` — repoint toolspec import
- Modify: `mypalclara/adapters/cli/commands.py:511` — repoint `gen_uuid` import only

---

## Task 1: Failing architecture test

**Files:**
- Modify: `tests/architecture/test_engine_boundary.py`

- [ ] **Step 1: Add the failing test**

Append this test (reuse the file's existing `CLIENT_PACKAGES`/AST helpers if present; otherwise this
is self-contained):

```python
import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CLIENT_DIRS = [
    _REPO_ROOT / "mypalclara" / "adapters",
    _REPO_ROOT / "mypalclara" / "web",
    _REPO_ROOT / "mypalclara" / "services" / "voice",
]
# Modules the client must NOT import (they live in engine packages deleted at the cut)
_FORBIDDEN_MODULES = {"mypalclara.core.platform", "mypalclara.tools._base"}
# Names the client must NOT import from these engine modules
_FORBIDDEN_NAMES = {"mypalclara.db.models": {"gen_uuid"}}


def _iter_client_py():
    for base in _CLIENT_DIRS:
        if base.exists():
            yield from base.rglob("*.py")


def test_client_does_not_import_relocated_shared_code():
    violations = []
    for path in _iter_client_py():
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module in _FORBIDDEN_MODULES:
                    violations.append(f"{path}: imports {node.module}")
                bad = _FORBIDDEN_NAMES.get(node.module, set())
                for alias in node.names:
                    if alias.name in bad:
                        violations.append(f"{path}: imports {alias.name} from {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in _FORBIDDEN_MODULES:
                        violations.append(f"{path}: imports {alias.name}")
    assert not violations, "Client imports relocated shared code from engine:\n" + "\n".join(violations)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `poetry run pytest tests/architecture/test_engine_boundary.py::test_client_does_not_import_relocated_shared_code -v`
Expected: FAIL listing 4 violations (cli/adapter.py, discord/adapter.py, cli/tools.py, cli/commands.py).

---

## Task 2: Create the `client_common` package + platform contracts

**Files:**
- Create: `mypalclara/client_common/__init__.py`
- Create: `mypalclara/client_common/platform.py`

- [ ] **Step 1: Create `mypalclara/client_common/__init__.py`**

```python
"""Client-side shared utilities, vendored out of engine packages.

These were relocated from `mypalclara.core` / `mypalclara.tools` / `mypalclara.db`
so the client no longer imports engine internals (engine owns the DB and runtime;
clients talk to it over the API). Keep this package engine-import-free.
"""

from mypalclara.client_common.ids import gen_uuid
from mypalclara.client_common.platform import (
    PlatformAdapter,
    PlatformContext,
    PlatformMessage,
)
from mypalclara.client_common.toolspec import ToolContext, ToolDef

__all__ = [
    "gen_uuid",
    "PlatformAdapter",
    "PlatformContext",
    "PlatformMessage",
    "ToolContext",
    "ToolDef",
]
```

- [ ] **Step 2: Create `mypalclara/client_common/platform.py`**

Copy `mypalclara/core/platform.py` **lines 1–141 verbatim** (the module docstring, the stdlib
imports, and the `PlatformMessage`, `PlatformContext`, and `PlatformAdapter` classes). **Stop before
`class APIAdapter`** (line 143) — the client importers use only the three above. The copied imports
are stdlib only (`abc`, `dataclasses`, `datetime`, `typing`), so the file is already engine-free.

- [ ] **Step 3: Verify the copy imports cleanly**

Run: `poetry run python -c "from mypalclara.client_common.platform import PlatformAdapter, PlatformContext, PlatformMessage; print('ok')"`
Expected: `ok`

---

## Task 3: Create `toolspec.py` (engine-free `ToolContext`/`ToolDef`)

**Files:**
- Create: `mypalclara/client_common/toolspec.py`

- [ ] **Step 1: Copy the dataclasses, dropping the engine TYPE_CHECKING import**

Copy `ToolContext` and `ToolDef` from `mypalclara/tools/_base.py` verbatim, BUT replace the engine
reference: delete the `if TYPE_CHECKING: from mypalclara.core.llm.tools.schema import ToolSchema`
block, and change any `ToolSchema` annotation to `Any`. Header:

```python
"""Client-side copy of the tool dataclasses (ToolContext, ToolDef).

Vendored from `mypalclara.tools._base` minus the engine-only ToolSchema type ref,
so the client carries no engine import.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable
```

Then paste the two `@dataclass` bodies (`ToolContext`, `ToolDef`) exactly as in `tools/_base.py`,
substituting `Any` wherever `ToolSchema` appeared.

- [ ] **Step 2: Verify**

Run: `poetry run python -c "from mypalclara.client_common.toolspec import ToolContext, ToolDef; print('ok')"`
Expected: `ok`

---

## Task 4: Create `ids.py` (`gen_uuid`)

**Files:**
- Create: `mypalclara/client_common/ids.py`

- [ ] **Step 1: Write the module**

```python
"""Client-side id helpers, vendored from mypalclara.db.models."""

from __future__ import annotations

import uuid


def gen_uuid() -> str:
    return str(uuid.uuid4())
```

- [ ] **Step 2: Verify**

Run: `poetry run python -c "from mypalclara.client_common.ids import gen_uuid; print(len(gen_uuid()))"`
Expected: `36`

---

## Task 5: Repoint the 4 client import sites

**Files:**
- Modify: `mypalclara/adapters/cli/adapter.py:18`
- Modify: `mypalclara/adapters/discord/adapter.py:18`
- Modify: `mypalclara/adapters/cli/tools.py:23`
- Modify: `mypalclara/adapters/cli/commands.py:511`

- [ ] **Step 1: cli/adapter.py and discord/adapter.py — both line 18**

Replace:
```python
from mypalclara.core.platform import PlatformAdapter, PlatformContext, PlatformMessage
```
with:
```python
from mypalclara.client_common.platform import PlatformAdapter, PlatformContext, PlatformMessage
```

- [ ] **Step 2: cli/tools.py line 23**

Replace:
```python
from mypalclara.tools._base import ToolContext, ToolDef
```
with:
```python
from mypalclara.client_common.toolspec import ToolContext, ToolDef
```

- [ ] **Step 3: cli/commands.py line 511 — the `gen_uuid` import ONLY**

Replace the in-function import:
```python
                    from mypalclara.db.models import gen_uuid
```
with:
```python
                    from mypalclara.client_common.ids import gen_uuid
```
Do NOT touch the other `from mypalclara.db.models import ...` lines (206/497/574/616) — those are
`PlatformLink`/`CanonicalUser` and belong to Sub-plan 3.

---

## Task 6: Verify boundary + tests, then commit

- [ ] **Step 1: Architecture test now passes**

Run: `poetry run pytest tests/architecture/test_engine_boundary.py -v`
Expected: all pass, including `test_client_does_not_import_relocated_shared_code`.

- [ ] **Step 2: Client import smoke**

Run: `poetry run python -c "import mypalclara.adapters.cli.adapter, mypalclara.adapters.discord.adapter, mypalclara.adapters.cli.tools; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Lint + targeted tests**

Run: `poetry run ruff check mypalclara/client_common mypalclara/adapters tests/architecture && poetry run ruff format mypalclara/client_common`
Run: `poetry run pytest tests/architecture tests/adapters -q` (skip `tests/adapters` if absent)
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add mypalclara/client_common tests/architecture/test_engine_boundary.py \
  mypalclara/adapters/cli/adapter.py mypalclara/adapters/discord/adapter.py \
  mypalclara/adapters/cli/tools.py mypalclara/adapters/cli/commands.py
git commit -m "refactor(client): vendor shared contracts into client_common; drop engine imports"
```

---

## Definition of done

`mypalclara/client_common/` holds the 3 vendored modules; the 4 client imports point at it; the new
architecture test is green; the client still boots in the monorepo. No engine API changes; no DB
rewire (that's Sub-plans 2–3).
