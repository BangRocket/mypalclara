"""Adapter manifest system for declarative adapter metadata.

This module provides a registry and decorator system for platform adapters,
allowing them to declare their capabilities, requirements, and metadata
in a standardized way.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypeVar

from mypalclara.config.logging import get_logger

logger = get_logger("adapters.manifest")

# Type variable for decorated classes
T = TypeVar("T")

# Global adapter registry (stores (class, manifest) tuples)
_adapter_registry: dict[str, tuple[type, AdapterManifest]] = {}


@dataclass
class AdapterManifest:
    """Declarative metadata for a platform adapter.

    Attributes:
        name: Unique adapter identifier (e.g., "discord", "telegram")
        platform: Platform name this adapter connects to
        version: Semantic version string (e.g., "1.0.0")
        display_name: Human-readable name (e.g., "Discord")
        description: Short description of the adapter
        icon: Emoji or icon representing the platform
        capabilities: List of supported features (streaming, attachments, etc.)
        required_env: Environment variables required for operation
        optional_env: Optional environment variables for additional features
        python_packages: Required Python packages (for documentation)
        config_schema: JSON Schema for adapter configuration (optional)
        author: Adapter author/maintainer
        homepage: URL for adapter documentation
        tags: Searchable tags for the adapter
    """

    name: str
    platform: str
    version: str = "1.0.0"
    display_name: str | None = None
    description: str = ""
    icon: str = "🔌"
    capabilities: list[str] = field(default_factory=lambda: ["streaming"])
    required_env: list[str] = field(default_factory=list)
    optional_env: list[str] = field(default_factory=list)
    python_packages: list[str] = field(default_factory=list)
    config_schema: dict[str, Any] | None = None
    author: str | None = None
    homepage: str | None = None
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Set defaults after initialization."""
        if self.display_name is None:
            self.display_name = self.name.title()

    def to_dict(self) -> dict[str, Any]:
        """Convert manifest to dictionary for serialization.

        Returns:
            Dict representation of the manifest
        """
        return {
            "name": self.name,
            "platform": self.platform,
            "version": self.version,
            "display_name": self.display_name,
            "description": self.description,
            "icon": self.icon,
            "capabilities": self.capabilities,
            "required_env": self.required_env,
            "optional_env": self.optional_env,
            "python_packages": self.python_packages,
            "config_schema": self.config_schema,
            "author": self.author,
            "homepage": self.homepage,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdapterManifest:
        """Create manifest from dictionary.

        Args:
            data: Dict with manifest fields

        Returns:
            AdapterManifest instance
        """
        return cls(
            name=data["name"],
            platform=data["platform"],
            version=data.get("version", "1.0.0"),
            display_name=data.get("display_name"),
            description=data.get("description", ""),
            icon=data.get("icon", "🔌"),
            capabilities=data.get("capabilities", ["streaming"]),
            required_env=data.get("required_env", []),
            optional_env=data.get("optional_env", []),
            python_packages=data.get("python_packages", []),
            config_schema=data.get("config_schema"),
            author=data.get("author"),
            homepage=data.get("homepage"),
            tags=data.get("tags", []),
        )


def adapter(manifest: AdapterManifest):
    """Decorator to register an adapter class with its manifest.

    Usage:
        @adapter(AdapterManifest(
            name="discord",
            platform="discord",
            version="1.0.0",
            capabilities=["streaming", "attachments", "reactions"],
            required_env=["DISCORD_BOT_TOKEN"],
        ))
        class DiscordGatewayClient(GatewayClient):
            ...

    Args:
        manifest: AdapterManifest describing the adapter

    Returns:
        Decorator function that registers the class
    """

    def decorator(cls: type[T]) -> type[T]:
        # Store manifest on the class
        cls.__adapter_manifest__ = manifest  # type: ignore

        # Register in global registry (cls, manifest) order for easier unpacking
        _adapter_registry[manifest.name] = (cls, manifest)
        logger.debug(f"Registered adapter: {manifest.name} ({manifest.display_name})")

        return cls

    return decorator


def get_adapter(name: str) -> tuple[type, AdapterManifest] | None:
    """Get an adapter by name from the registry.

    Args:
        name: Adapter name (e.g., "discord", "telegram")

    Returns:
        Tuple of (class, manifest) or None if not found
    """
    return _adapter_registry.get(name)


def get_adapter_class(name: str) -> type | None:
    """Get an adapter class by name.

    Args:
        name: Adapter name

    Returns:
        Adapter class or None if not found
    """
    entry = _adapter_registry.get(name)
    return entry[0] if entry else None


def get_adapter_manifest(name: str) -> AdapterManifest | None:
    """Get an adapter manifest by name.

    Args:
        name: Adapter name

    Returns:
        AdapterManifest or None if not found
    """
    entry = _adapter_registry.get(name)
    return entry[1] if entry else None


def list_adapters() -> list[str]:
    """List all registered adapter names.

    Returns:
        List of adapter names
    """
    return list(_adapter_registry.keys())


def get_all_manifests() -> list[AdapterManifest]:
    """Get all registered adapter manifests.

    Returns:
        List of all registered AdapterManifest objects
    """
    return [manifest for _, manifest in _adapter_registry.values()]


def get_adapters_by_capability(capability: str) -> list[AdapterManifest]:
    """Get all adapters that support a specific capability.

    Args:
        capability: Capability name (e.g., "streaming", "attachments")

    Returns:
        List of manifests for adapters with that capability
    """
    return [manifest for _, manifest in _adapter_registry.values() if capability in manifest.capabilities]


def get_adapters_by_platform(platform: str) -> list[AdapterManifest]:
    """Get all adapters for a specific platform.

    Args:
        platform: Platform name (e.g., "discord", "slack")

    Returns:
        List of manifests for that platform
    """
    return [manifest for _, manifest in _adapter_registry.values() if manifest.platform == platform]


def get_adapters_by_tag(tag: str) -> list[AdapterManifest]:
    """Get all adapters with a specific tag.

    Args:
        tag: Tag to search for

    Returns:
        List of manifests with that tag
    """
    return [manifest for _, manifest in _adapter_registry.values() if tag in manifest.tags]


def validate_adapter_env(name: str) -> tuple[bool, list[str]]:
    """Check if required environment variables are set for an adapter.

    Args:
        name: Adapter name

    Returns:
        Tuple of (all_set, missing_vars)
    """
    import os

    manifest = get_adapter_manifest(name)
    if manifest is None:
        return False, [f"Adapter '{name}' not found"]

    missing = []
    for env_var in manifest.required_env:
        if not os.getenv(env_var):
            missing.append(env_var)

    return len(missing) == 0, missing


def get_adapter_info(name: str) -> dict[str, Any] | None:
    """Get comprehensive info about an adapter.

    Args:
        name: Adapter name

    Returns:
        Dict with manifest data and runtime info, or None if not found
    """
    entry = _adapter_registry.get(name)
    if entry is None:
        return None

    cls, manifest = entry

    # Check environment
    env_ok, missing_env = validate_adapter_env(name)

    return {
        **manifest.to_dict(),
        "class": cls.__name__,
        "module": cls.__module__,
        "env_configured": env_ok,
        "missing_env": missing_env,
    }


def discover_adapters() -> None:
    """Import all adapter modules to trigger registration.

    This function imports known adapter modules so their @adapter
    decorators execute and register them in the global registry.
    """
    adapter_modules = [
        "mypalclara.adapters.discord.gateway_client",
        "mypalclara.adapters.cli.gateway_client",
        "mypalclara.adapters.teams.gateway_client",
        "mypalclara.adapters.telegram.gateway_client",
        "mypalclara.adapters.slack.gateway_client",
        "mypalclara.adapters.whatsapp.gateway_client",
        "mypalclara.adapters.signal.gateway_client",
        "mypalclara.adapters.matrix.gateway_client",
        "mypalclara.adapters.game",
    ]

    for module_name in adapter_modules:
        try:
            __import__(module_name)
            logger.debug(f"Discovered adapter module: {module_name}")
        except ImportError as e:
            # Module not installed or doesn't exist yet
            logger.debug(f"Adapter module not available: {module_name} ({e})")
        except Exception as e:
            logger.warning(f"Error loading adapter module {module_name}: {e}")


def clear_registry() -> None:
    """Clear the adapter registry (for testing)."""
    _adapter_registry.clear()
