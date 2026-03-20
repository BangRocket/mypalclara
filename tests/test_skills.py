"""Tests for the skills lazy-loading system."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from mypalclara.core.skills.registry import SkillRegistry


@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    """Create a temporary skills directory with example skills."""
    # Skill with valid frontmatter
    skill_a = tmp_path / "code_review"
    skill_a.mkdir()
    (skill_a / "SKILL.md").write_text(
        "---\n"
        "name: code_review\n"
        "description: Review code for quality and security\n"
        "---\n"
        "\n"
        "## Code Review Instructions\n"
        "\n"
        "Check correctness, security, and performance.\n"
    )

    # Another skill
    skill_b = tmp_path / "summarize"
    skill_b.mkdir()
    (skill_b / "SKILL.md").write_text(
        "---\n"
        "name: summarize\n"
        "description: Summarize long text into key points\n"
        "---\n"
        "\n"
        "## Summarization Instructions\n"
        "\n"
        "Extract the main ideas and present them concisely.\n"
    )

    return tmp_path


@pytest.fixture
def registry(skills_dir: Path) -> SkillRegistry:
    """Create a SkillRegistry pointed at the temp skills dir."""
    return SkillRegistry(skills_dir=skills_dir)


class TestSkillRegistry:
    def test_get_catalog(self, registry: SkillRegistry) -> None:
        """get_catalog returns name+description for each skill dir with SKILL.md."""
        catalog = registry.get_catalog()
        assert len(catalog) == 2
        names = {item["name"] for item in catalog}
        assert names == {"code_review", "summarize"}
        for item in catalog:
            assert "description" in item
            assert len(item["description"]) > 0

    def test_load_skill_returns_body_without_frontmatter(self, registry: SkillRegistry) -> None:
        """load_skill returns the markdown body, excluding YAML frontmatter."""
        body = registry.load_skill("code_review")
        assert body is not None
        assert "## Code Review Instructions" in body
        assert "Check correctness, security, and performance." in body
        # Frontmatter markers and metadata should be stripped
        assert "---" not in body
        assert "name: code_review" not in body

    def test_load_nonexistent_skill_returns_none(self, registry: SkillRegistry) -> None:
        """load_skill returns None for a skill that doesn't exist."""
        result = registry.load_skill("nonexistent_skill")
        assert result is None

    def test_list_skills(self, registry: SkillRegistry) -> None:
        """list_skills returns sorted list of skill names."""
        names = registry.list_skills()
        assert isinstance(names, list)
        assert set(names) == {"code_review", "summarize"}

    def test_catalog_is_cached(self, registry: SkillRegistry) -> None:
        """get_catalog caches results; second call returns same object."""
        first = registry.get_catalog()
        second = registry.get_catalog()
        assert first is second

    def test_invalidate_clears_cache(self, registry: SkillRegistry) -> None:
        """invalidate() forces a fresh scan on the next get_catalog call."""
        first = registry.get_catalog()
        registry.invalidate()
        second = registry.get_catalog()
        # Same content but different object (re-scanned)
        assert first is not second
        assert len(second) == 2

    def test_format_catalog_for_prompt(self, registry: SkillRegistry) -> None:
        """format_catalog_for_prompt produces markdown with skill names and descriptions."""
        text = registry.format_catalog_for_prompt()
        assert "code_review" in text
        assert "summarize" in text
        assert "Review code" in text

    def test_empty_skills_dir(self, tmp_path: Path) -> None:
        """Registry with empty skills dir returns empty catalog."""
        reg = SkillRegistry(skills_dir=tmp_path)
        assert reg.get_catalog() == []
        assert reg.list_skills() == []
        assert reg.format_catalog_for_prompt() == ""

    def test_dir_without_skill_md_is_ignored(self, tmp_path: Path) -> None:
        """Directories without SKILL.md are silently skipped."""
        (tmp_path / "incomplete_skill").mkdir()
        (tmp_path / "incomplete_skill" / "README.md").write_text("not a skill")
        reg = SkillRegistry(skills_dir=tmp_path)
        assert reg.get_catalog() == []

    def test_parse_frontmatter_missing_fields(self, tmp_path: Path) -> None:
        """Skill with missing frontmatter fields uses directory name as fallback."""
        skill_dir = tmp_path / "my_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\n" "description: A skill with no name field\n" "---\n" "\n" "Body content here.\n"
        )
        reg = SkillRegistry(skills_dir=tmp_path)
        catalog = reg.get_catalog()
        assert len(catalog) == 1
        assert catalog[0]["name"] == "my_skill"
