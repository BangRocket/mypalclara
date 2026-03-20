"""Skills lazy-loading registry.

Scans a workspace directory for skill definitions (SKILL.md files with YAML
frontmatter).  Only a lightweight catalog (name + description) is exposed for
system-prompt injection; full skill content is loaded on demand via
``load_skill()``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class SkillRegistry:
    """Registry for workspace skill definitions.

    Each skill lives in its own subdirectory under ``skills_dir`` and must
    contain a ``SKILL.md`` file with YAML frontmatter (``name``, ``description``).
    """

    def __init__(self, skills_dir: Path | None = None) -> None:
        self._skills_dir = skills_dir or Path("mypalclara/workspace/skills")
        self._catalog: list[dict[str, str]] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_catalog(self) -> list[dict[str, str]]:
        """Return cached catalog of ``{"name": ..., "description": ...}`` dicts."""
        if self._catalog is None:
            self._catalog = self._scan_catalog()
        return self._catalog

    def load_skill(self, name: str) -> str | None:
        """Return the full body (after frontmatter) of a skill, or ``None``."""
        path = self._skills_dir / name / "SKILL.md"
        if not path.is_file():
            return None
        _, body = self._parse_frontmatter(path)
        return body

    def list_skills(self) -> list[str]:
        """Return sorted list of available skill names."""
        return [item["name"] for item in self.get_catalog()]

    def invalidate(self) -> None:
        """Clear the cached catalog so the next access re-scans the directory."""
        self._catalog = None

    def format_catalog_for_prompt(self) -> str:
        """Format catalog as markdown suitable for system-prompt injection."""
        catalog = self.get_catalog()
        if not catalog:
            return ""
        lines = ["## Available Skills", ""]
        lines.append("| Skill | Description |")
        lines.append("|-------|-------------|")
        for item in catalog:
            lines.append(f"| `{item['name']}` | {item['description']} |")
        lines.append("")
        lines.append("Use `load_skill(name)` to get full instructions for a skill.")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _scan_catalog(self) -> list[dict[str, str]]:
        """Walk ``skills_dir`` and collect frontmatter from each SKILL.md."""
        if not self._skills_dir.is_dir():
            return []

        catalog: list[dict[str, str]] = []
        for child in sorted(self._skills_dir.iterdir()):
            if not child.is_dir():
                continue
            skill_file = child / "SKILL.md"
            if not skill_file.is_file():
                continue
            meta, _ = self._parse_frontmatter(skill_file)
            name = meta.get("name", child.name)
            description = meta.get("description", "")
            catalog.append({"name": name, "description": description})
        return catalog

    @staticmethod
    def _parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
        """Parse simple YAML frontmatter delimited by ``---``.

        Returns:
            (metadata_dict, body_string)
        """
        text = path.read_text(encoding="utf-8")
        meta: dict[str, str] = {}

        if not text.startswith("---"):
            return meta, text

        # Find closing ---
        end_idx = text.find("---", 3)
        if end_idx == -1:
            return meta, text

        frontmatter_block = text[3:end_idx].strip()
        body = text[end_idx + 3 :].lstrip("\n")

        for line in frontmatter_block.splitlines():
            line = line.strip()
            if ":" in line:
                key, _, value = line.partition(":")
                meta[key.strip()] = value.strip()

        return meta, body


# ------------------------------------------------------------------
# Module-level singleton
# ------------------------------------------------------------------

_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    """Return (or create) the module-level singleton ``SkillRegistry``."""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry
