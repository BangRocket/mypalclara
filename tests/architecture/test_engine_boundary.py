"""Architecture boundary test for the client repo.

The client is where Clara shows up: adapters, voice, the client SDK. It reaches
the engine only over the wire (`GatewayClient` WebSocket, `EngineApiClient`
HTTP) and through the shared `mypal_protocol` contract. It must never import
engine code or carry engine infrastructure.

Three rules, all checked on every `.py` file under `mypalclara/`:

1. Every `mypalclara.*` import resolves to a module that exists in THIS repo.
   The engine's Python package is also named `mypalclara`, so an import of
   `mypalclara.core...` or `mypalclara.gateway...` would only work with the
   engine on `sys.path`. Resolving against the repo catches that by
   construction, whatever the engine names its packages in future.
2. No import of an engine or memory-service distribution, and no import of
   the infrastructure SDKs (database, vector store, graph, LLM orchestration)
   that only the engine should hold.
3. The engine's package directories do not exist under the client package.

The `test_detector_*` tests feed the checker known-bad source so a checker
that silently matches nothing fails loudly instead of passing.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
PKG_NAME = "mypalclara"
PKG_ROOT = REPO_ROOT / PKG_NAME

# Engine-side distributions and the infrastructure only the engine may hold.
FORBIDDEN_ROOTS = {
    # engine / memory service code
    "mypal_engine",
    "clara_core",
    "mypalace",
    "mypalace_client",
    # persistence
    "sqlalchemy",
    "alembic",
    "psycopg2",
    "asyncpg",
    "redis",
    # memory stores
    "qdrant_client",
    "falkordb",
    "pgvector",
    # LLM orchestration (the engine decides what Clara says)
    "anthropic",
    "langchain",
    "langchain_core",
    "langchain_openai",
    "langchain_anthropic",
    "langchain_aws",
    # sandbox
    "docker",
}

# Directories that belong to the engine and must not reappear here.
ENGINE_DIRS = [
    "core",
    "db",
    "gateway",
    "sandbox",
    "tools",
    "ambient",
    "workspace",
    "services/email",
    "services/backup",
    "services/proactive",
    "services/blog",
]


def _absolute_imports(source: str, filename: str = "<src>") -> set[str]:
    """Every absolutely-imported module name in `source`, including lazy ones.

    `from pkg import name` yields both `pkg` and `pkg.name`, because `name`
    may be a submodule (`from mypalclara import core`).
    """
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source, filename=filename)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module)
            modules.update(f"{node.module}.{alias.name}" for alias in node.names)
    return modules


def _resolves_in_repo(module: str) -> bool:
    """True if `module` is a package or module file in this repo."""
    path = REPO_ROOT.joinpath(*module.split("."))
    return (path / "__init__.py").exists() or path.with_suffix(".py").exists()


def _violations(source: str, filename: str = "<src>") -> set[str]:
    """Imports in `source` that cross the client/engine boundary."""
    bad: set[str] = set()
    for module in _absolute_imports(source, filename):
        parts = module.split(".")
        if parts[0] in FORBIDDEN_ROOTS:
            bad.add(module)
        elif parts[0] == PKG_NAME and len(parts) > 1:
            # `from mypalclara.x import name`: `mypalclara.x.name` is usually an
            # attribute, not a module. Only the module part has to resolve, so
            # accept the import if it or its parent is a real module here.
            if not (_resolves_in_repo(module) or (len(parts) > 2 and _resolves_in_repo(".".join(parts[:-1])))):
                bad.add(module)
    return bad


def _client_files() -> list[pathlib.Path]:
    return sorted(PKG_ROOT.rglob("*.py"))


def test_client_package_is_scanned():
    # Guards against the checker passing because it found nothing to check.
    files = _client_files()
    assert len(files) > 20, f"expected the client package under {PKG_ROOT}, found {len(files)} files"
    assert (PKG_ROOT / "adapters" / "base.py").exists()


def test_client_imports_no_engine_code():
    offenders = {}
    for path in _client_files():
        bad = _violations(path.read_text(encoding="utf-8"), str(path))
        if bad:
            offenders[path.relative_to(REPO_ROOT).as_posix()] = sorted(bad)
    assert not offenders, (
        "Client files import engine code or engine-only infrastructure. "
        "Use EngineApiClient (HTTP) or GatewayClient (WS) instead:\n"
        + "\n".join(f"  {f}: {mods}" for f, mods in sorted(offenders.items()))
    )


def test_client_holds_no_persona():
    # Who Clara is lives only in the engine's character/ directory.
    assert not (
        REPO_ROOT / "personalities"
    ).exists(), "personalities/ reappeared; personas live in mypal-engine/character/"
    offenders = [
        p.relative_to(REPO_ROOT).as_posix()
        for p in [*PKG_ROOT.rglob("*.py"), *PKG_ROOT.rglob("*.md"), *PKG_ROOT.rglob("*.txt")]
        if "You are Clara" in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert not offenders, f"Persona text in the client (it belongs in mypal-engine/character/): {offenders}"


def test_engine_directories_do_not_exist_in_client():
    present = [d for d in ENGINE_DIRS if (PKG_ROOT / d).exists()]
    assert not present, f"Engine directories reappeared under {PKG_NAME}/: {present}"


@pytest.mark.parametrize(
    "source",
    [
        "from mypalclara.core.memory_manager import MemoryManager",
        "import mypalclara.gateway.processor",
        "from mypalclara import db",
        "from mypalclara.db.models import Session",
        "def f():\n    from mypalclara.core.llm import make_llm\n",
        "try:\n    import mypalclara.sandbox\nexcept ImportError:\n    pass\n",
        "import mypal_engine.gateway",
        "from mypalace_client import PalaceClient",
        "import sqlalchemy",
        "from qdrant_client import QdrantClient",
        "from langchain_anthropic import ChatAnthropic",
    ],
)
def test_detector_flags_boundary_violations(source):
    assert _violations(source), f"checker missed a violation: {source!r}"


@pytest.mark.parametrize(
    "source",
    [
        "from mypalclara.adapters.base import GatewayClient",
        "from mypalclara.client_common.engine_client import EngineApiClient",
        "from mypalclara.client_common import engine_client",
        "import mypalclara.config.logging",
        "from mypal_protocol import RegisterMessage",
        "import discord",
        "import httpx",
        "from . import sibling",
    ],
)
def test_detector_allows_client_imports(source):
    assert not _violations(source), f"checker rejected a legitimate import: {source!r}"
