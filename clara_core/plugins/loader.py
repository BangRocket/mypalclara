"""Plugin loading and discovery.

Handles dynamic loading of plugins from various sources:
- Local Python packages
- Installed packages
- Plugin directories
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from config.logging import get_logger

if TYPE_CHECKING:
    from clara_core.plugins.types import ClaraPlugin

logger = get_logger("plugins.loader")


class PluginLoader:
    """Loads Clara plugins from various sources.

    Supports:
    - Python modules
    - Package entry points
    - Plugin directories
    """

    def __init__(self, plugin_dirs: list[str | Path] | None = None) -> None:
        """Initialize the plugin loader.

        Args:
            plugin_dirs: Directories to search for plugins
        """
        self.plugin_dirs = [Path(d) for d in (plugin_dirs or [])]
        self._loaded: dict[str, "ClaraPlugin"] = {}

    def load_from_module(self, module_name: str) -> "ClaraPlugin | None":
        """Load a plugin from a Python module.

        The module should have a `plugin` attribute that is a ClaraPlugin instance.

        Args:
            module_name: Fully qualified module name

        Returns:
            The loaded plugin or None if loading failed
        """
        try:
            module = importlib.import_module(module_name)
            plugin = getattr(module, "plugin", None)

            if plugin is None:
                # Try looking for a create_plugin function
                create_plugin = getattr(module, "create_plugin", None)
                if create_plugin:
                    plugin = create_plugin()

            if plugin is None:
                logger.error(f"Module {module_name} has no 'plugin' attribute")
                return None

            self._loaded[plugin.id] = plugin
            logger.info(f"Loaded plugin: {plugin.name} ({plugin.id})")
            return plugin

        except ImportError as e:
            logger.error(f"Failed to import plugin module {module_name}: {e}")
            return None
        except Exception as e:
            logger.exception(f"Error loading plugin {module_name}: {e}")
            return None

    def load_from_file(self, file_path: str | Path) -> "ClaraPlugin | None":
        """Load a plugin from a Python file.

        Args:
            file_path: Path to the plugin file

        Returns:
            The loaded plugin or None if loading failed
        """
        path = Path(file_path)
        if not path.exists():
            logger.error(f"Plugin file not found: {path}")
            return None

        try:
            # Generate a unique module name
            module_name = f"clara_plugins.{path.stem}"

            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                logger.error(f"Could not load plugin from {path}")
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            plugin = getattr(module, "plugin", None)
            if plugin is None:
                create_plugin = getattr(module, "create_plugin", None)
                if create_plugin:
                    plugin = create_plugin()

            if plugin is None:
                logger.error(f"File {path} has no 'plugin' attribute")
                return None

            self._loaded[plugin.id] = plugin
            logger.info(f"Loaded plugin from file: {plugin.name}")
            return plugin

        except Exception as e:
            logger.exception(f"Error loading plugin from {path}: {e}")
            return None

    def load_from_directory(self, directory: str | Path) -> list["ClaraPlugin"]:
        """Load all plugins from a directory.

        Looks for Python files with 'plugin' in the name or __init__.py files
        in subdirectories.

        Args:
            directory: Directory to scan

        Returns:
            List of loaded plugins
        """
        path = Path(directory)
        if not path.exists():
            logger.warning(f"Plugin directory not found: {path}")
            return []

        plugins = []

        # Look for plugin files
        for file in path.glob("*_plugin.py"):
            plugin = self.load_from_file(file)
            if plugin:
                plugins.append(plugin)

        # Look for plugin packages (directories with __init__.py)
        for subdir in path.iterdir():
            if subdir.is_dir() and (subdir / "__init__.py").exists():
                plugin = self.load_from_file(subdir / "__init__.py")
                if plugin:
                    plugins.append(plugin)

        return plugins

    def discover_plugins(self) -> list["ClaraPlugin"]:
        """Discover and load plugins from all configured directories.

        Returns:
            List of all discovered plugins
        """
        plugins = []
        for directory in self.plugin_dirs:
            plugins.extend(self.load_from_directory(directory))
        return plugins

    def get_loaded(self) -> dict[str, "ClaraPlugin"]:
        """Get all loaded plugins.

        Returns:
            Dict mapping plugin ID to plugin
        """
        return dict(self._loaded)

    def get_plugin(self, plugin_id: str) -> "ClaraPlugin | None":
        """Get a loaded plugin by ID.

        Args:
            plugin_id: The plugin ID

        Returns:
            The plugin or None if not found
        """
        return self._loaded.get(plugin_id)


def load_plugin(source: str) -> "ClaraPlugin | None":
    """Convenience function to load a single plugin.

    Args:
        source: Module name or file path

    Returns:
        The loaded plugin or None if loading failed
    """
    loader = PluginLoader()

    # Check if it's a file path
    if source.endswith(".py") or "/" in source or "\\" in source:
        return loader.load_from_file(source)
    else:
        return loader.load_from_module(source)
