"""Tests for workspace file loading with budget management."""

from pathlib import Path

import pytest

from mypalclara.core.workspace_loader import WorkspaceFile, WorkspaceLoader


@pytest.fixture
def tmp_workspace(tmp_path):
    (tmp_path / "SOUL.md").write_text("Be warm and helpful.")
    (tmp_path / "IDENTITY.md").write_text("- **Name:** TestBot\n- **Emoji:** sparkle\n- **Vibe:** friendly")
    (tmp_path / "USER.md").write_text("Joshua likes coffee.")
    (tmp_path / "AGENTS.md").write_text("Always be concise.")
    return tmp_path


class TestWorkspaceLoading:
    def test_load_all_files(self, tmp_workspace):
        loader = WorkspaceLoader()
        files = loader.load(tmp_workspace, mode="full")
        names = [f.filename for f in files]
        assert "SOUL.md" in names
        assert "IDENTITY.md" in names
        assert "USER.md" in names
        assert "AGENTS.md" in names

    def test_missing_files_skipped(self, tmp_path):
        loader = WorkspaceLoader()
        files = loader.load(tmp_path, mode="full")
        assert len(files) == 0

    def test_minimal_mode_subset(self, tmp_workspace):
        (tmp_workspace / "TOOLS.md").write_text("Tool notes here.")
        (tmp_workspace / "MEMORY.md").write_text("Remember this.")
        loader = WorkspaceLoader()
        files = loader.load(tmp_workspace, mode="minimal")
        names = [f.filename for f in files]
        assert "SOUL.md" in names
        assert "IDENTITY.md" in names
        assert "TOOLS.md" not in names
        assert "MEMORY.md" not in names


class TestBudgetManagement:
    def test_large_file_truncated(self, tmp_path):
        (tmp_path / "SOUL.md").write_text("x" * 30_000)
        loader = WorkspaceLoader(per_file_max=20_000)
        files = loader.load(tmp_path)
        soul = [f for f in files if f.filename == "SOUL.md"][0]
        assert soul.was_truncated
        assert len(soul.content) < 25_000

    def test_total_budget_enforced(self, tmp_path):
        for name in ["SOUL.md", "AGENTS.md", "USER.md"]:
            (tmp_path / name).write_text("y" * 60_000)
        loader = WorkspaceLoader(per_file_max=60_000, total_max=100_000)
        files = loader.load(tmp_path)
        total = sum(len(f.content) for f in files)
        assert total <= 110_000


class TestIdentityParsing:
    def test_parse_structured_fields(self, tmp_workspace):
        loader = WorkspaceLoader()
        files = loader.load(tmp_workspace)
        identity = [f for f in files if f.filename == "IDENTITY.md"][0]
        assert identity.structured_fields is not None
        assert identity.structured_fields.get("name") == "TestBot"
        assert identity.structured_fields.get("emoji") == "sparkle"
        assert identity.structured_fields.get("vibe") == "friendly"

    def test_no_structured_fields_for_non_identity(self, tmp_workspace):
        loader = WorkspaceLoader()
        files = loader.load(tmp_workspace)
        soul = [f for f in files if f.filename == "SOUL.md"][0]
        assert soul.structured_fields is None
