"""Clara Plugin System.

Provides an extensible plugin API following OpenClaw's architecture.
Plugins can:
- Register channels
- Add tools
- Register lifecycle hooks
- Add HTTP routes
- Register services
- Add CLI commands
"""

from clara_core.plugins.loader import PluginLoader, load_plugin
from clara_core.plugins.manager import PluginManager, get_plugin_manager
from clara_core.plugins.types import (
    ClaraPlugin,
    ClaraPluginApi,
    PluginHook,
    PluginRuntime,
    ToolDefinition,
    ToolFactory,
)

__all__ = [
    # Types
    "ClaraPlugin",
    "ClaraPluginApi",
    "PluginHook",
    "PluginRuntime",
    "ToolDefinition",
    "ToolFactory",
    # Loader
    "PluginLoader",
    "load_plugin",
    # Manager
    "PluginManager",
    "get_plugin_manager",
]
