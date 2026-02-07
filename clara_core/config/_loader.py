"""YAML config file discovery and Pydantic settings source."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource


def find_config_file() -> Path | None:
    """Find clara.yaml using search order:
    1. CLARA_CONFIG env var (explicit path)
    2. ./clara.yaml (CWD)
    3. ./clara.yml (CWD alt)
    4. ~/.clara/clara.yaml (user home)
    """
    explicit = os.environ.get("CLARA_CONFIG")
    if explicit:
        p = Path(explicit)
        if p.is_file():
            return p
        return None

    candidates = [
        Path.cwd() / "clara.yaml",
        Path.cwd() / "clara.yml",
        Path.home() / ".clara" / "clara.yaml",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


class YamlSettingsSource(PydanticBaseSettingsSource):
    """Load settings from a YAML file."""

    def __init__(self, settings_cls: type[BaseSettings]) -> None:
        super().__init__(settings_cls)
        self._yaml_data: dict[str, Any] = {}
        config_path = find_config_file()
        if config_path is not None:
            with open(config_path) as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    self._yaml_data = data

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        val = self._yaml_data.get(field_name)
        return val, field_name, val is not None

    def __call__(self) -> dict[str, Any]:
        return self._yaml_data
