"""Plugin manager - coordinates plugin lifecycle and provides the API.

The PluginManager:
- Manages plugin registration and lifecycle
- Implements ClaraPluginApi for plugins to use
- Coordinates hooks and events
- Provides service registry
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, ClassVar

from config.logging import get_logger

if TYPE_CHECKING:
    from clara_core.channels.types import ChannelPlugin
    from clara_core.plugins.types import (
        ClaraPlugin,
        ClaraPluginApi,
        HttpRoute,
        PluginHook,
        PluginRuntime,
        ToolDefinition,
        ToolFactory,
    )

logger = get_logger("plugins.manager")


@dataclass
class PluginState:
    """State for a registered plugin."""

    plugin: "ClaraPlugin"
    registered: bool = False
    initialized: bool = False
    tools: list["ToolDefinition"] = field(default_factory=list)
    hooks: dict[str, list[Callable[..., Any]]] = field(default_factory=dict)
    http_routes: list["HttpRoute"] = field(default_factory=list)
    services: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class PluginManager:
    """Manages plugin lifecycle and provides the plugin API.

    This is the core of the plugin system. It:
    - Registers plugins and their functionality
    - Manages plugin lifecycle (init, cleanup)
    - Coordinates hook execution
    - Provides service registry
    """

    _instance: ClassVar["PluginManager | None"] = None

    def __init__(
        self,
        config_dir: str | Path = "~/.clara",
        data_dir: str | Path = "~/.clara/plugins",
        debug: bool = False,
    ) -> None:
        """Initialize the plugin manager.

        Args:
            config_dir: Configuration directory
            data_dir: Plugin data directory
            debug: Enable debug mode
        """
        self.config_dir = Path(config_dir).expanduser()
        self.data_dir = Path(data_dir).expanduser()
        self.debug = debug

        self._plugins: dict[str, PluginState] = {}
        self._tools: dict[str, "ToolDefinition"] = {}
        self._hooks: dict[str, list[Callable[..., Any]]] = {}
        self._http_routes: list["HttpRoute"] = []
        self._gateway_methods: dict[str, Callable[..., Any]] = {}
        self._services: dict[str, Any] = {}
        self._providers: dict[str, dict[str, Any]] = {}
        self._commands: dict[str, Callable[..., Any]] = {}
        self._cli_registrations: list[Callable[..., Any]] = []
        self._model_providers: dict[str, Any] = {}

    @classmethod
    def get_instance(cls) -> "PluginManager":
        """Get the singleton manager instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        cls._instance = None

    def _get_runtime(self, plugin_id: str) -> "PluginRuntime":
        """Create runtime info for a plugin."""
        import os

        from clara_core.plugins.types import PluginRuntime

        plugin_state = self._plugins.get(plugin_id)
        version = plugin_state.plugin.version if plugin_state else "0.0.0"

        return PluginRuntime(
            plugin_id=plugin_id,
            version=version,
            config_dir=str(self.config_dir),
            data_dir=str(self.data_dir / plugin_id),
            debug=self.debug,
            gateway_url=os.getenv("CLARA_GATEWAY_URL"),
        )

    def _create_api(self, plugin_id: str) -> "ClaraPluginApi":
        """Create a plugin API instance for a specific plugin."""
        return _PluginApiImpl(self, plugin_id)

    def register_plugin(self, plugin: "ClaraPlugin") -> bool:
        """Register a plugin.

        Args:
            plugin: The plugin to register

        Returns:
            True if registration succeeded
        """
        if plugin.id in self._plugins:
            logger.warning(f"Plugin {plugin.id} is already registered")
            return False

        # Check dependencies
        for dep in plugin.dependencies:
            if dep not in self._plugins:
                logger.error(f"Plugin {plugin.id} requires {dep} which is not loaded")
                return False

        state = PluginState(plugin=plugin)
        self._plugins[plugin.id] = state

        # Call register function if present
        if plugin.register:
            try:
                api = self._create_api(plugin.id)
                plugin.register(api)
                state.registered = True
                logger.info(f"Registered plugin: {plugin.name}")
            except Exception as e:
                state.error = str(e)
                logger.exception(f"Error registering plugin {plugin.id}: {e}")
                return False

        return True

    async def init_plugin(self, plugin_id: str) -> bool:
        """Initialize a plugin (call its async init).

        Args:
            plugin_id: The plugin to initialize

        Returns:
            True if initialization succeeded
        """
        state = self._plugins.get(plugin_id)
        if not state:
            return False

        if state.initialized:
            return True

        if state.plugin.init:
            try:
                result = state.plugin.init()
                if asyncio.iscoroutine(result):
                    await result
                state.initialized = True
                logger.info(f"Initialized plugin: {state.plugin.name}")
            except Exception as e:
                state.error = str(e)
                logger.exception(f"Error initializing plugin {plugin_id}: {e}")
                return False

        return True

    async def cleanup_plugin(self, plugin_id: str) -> None:
        """Cleanup a plugin.

        Args:
            plugin_id: The plugin to cleanup
        """
        state = self._plugins.get(plugin_id)
        if not state:
            return

        if state.plugin.cleanup:
            try:
                result = state.plugin.cleanup()
                if asyncio.iscoroutine(result):
                    await result
                logger.info(f"Cleaned up plugin: {state.plugin.name}")
            except Exception as e:
                logger.exception(f"Error cleaning up plugin {plugin_id}: {e}")

        state.initialized = False

    async def init_all(self) -> dict[str, bool]:
        """Initialize all registered plugins.

        Returns:
            Dict mapping plugin ID to success status
        """
        results = {}
        for plugin_id in self._plugins:
            results[plugin_id] = await self.init_plugin(plugin_id)
        return results

    async def cleanup_all(self) -> None:
        """Cleanup all plugins."""
        for plugin_id in self._plugins:
            await self.cleanup_plugin(plugin_id)

    async def emit_hook(
        self,
        hook: "PluginHook",
        *args: Any,
        **kwargs: Any,
    ) -> list[Any]:
        """Emit a hook event to all registered handlers.

        Args:
            hook: The hook type
            *args: Positional arguments for handlers
            **kwargs: Keyword arguments for handlers

        Returns:
            List of results from handlers
        """
        hook_key = str(hook.value) if hasattr(hook, "value") else str(hook)
        handlers = self._hooks.get(hook_key, [])
        results = []

        for handler in handlers:
            try:
                result = handler(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    result = await result
                results.append(result)
            except Exception as e:
                logger.exception(f"Error in hook handler for {hook_key}: {e}")
                results.append(None)

        return results

    def get_all_tools(self) -> dict[str, "ToolDefinition"]:
        """Get all registered tools."""
        return dict(self._tools)

    def get_tool(self, name: str) -> "ToolDefinition | None":
        """Get a tool by name."""
        return self._tools.get(name)

    def get_http_routes(self) -> list["HttpRoute"]:
        """Get all registered HTTP routes."""
        return list(self._http_routes)

    def get_gateway_methods(self) -> dict[str, Callable[..., Any]]:
        """Get all registered gateway methods."""
        return dict(self._gateway_methods)

    def get_service(self, key: str) -> Any:
        """Get a registered service."""
        return self._services.get(key)

    def get_command(self, name: str) -> Callable[..., Any] | None:
        """Get a registered command."""
        return self._commands.get(name)

    def get_model_provider(self, provider_id: str) -> Any:
        """Get a registered model provider."""
        return self._model_providers.get(provider_id)

    def get_plugin_status(self) -> dict[str, dict[str, Any]]:
        """Get status of all plugins."""
        return {
            pid: {
                "name": state.plugin.name,
                "version": state.plugin.version,
                "registered": state.registered,
                "initialized": state.initialized,
                "error": state.error,
                "tools": len(state.tools),
            }
            for pid, state in self._plugins.items()
        }


class _PluginApiImpl:
    """Implementation of ClaraPluginApi for a specific plugin."""

    def __init__(self, manager: PluginManager, plugin_id: str) -> None:
        self._manager = manager
        self._plugin_id = plugin_id

    @property
    def runtime(self) -> "PluginRuntime":
        return self._manager._get_runtime(self._plugin_id)

    def register_channel(self, plugin: "ChannelPlugin[Any]") -> None:
        from clara_core.channels import get_channel_registry
        registry = get_channel_registry()
        registry.register(plugin)

    def register_tool(self, tool: "ToolDefinition | ToolFactory") -> None:
        from clara_core.plugins.types import ToolDefinition

        if callable(tool) and not isinstance(tool, ToolDefinition):
            # It's a factory function
            tools = tool()
            for t in tools:
                self._manager._tools[t.name] = t
                state = self._manager._plugins.get(self._plugin_id)
                if state:
                    state.tools.append(t)
        else:
            # It's a single tool definition
            self._manager._tools[tool.name] = tool
            state = self._manager._plugins.get(self._plugin_id)
            if state:
                state.tools.append(tool)

    def register_hook(
        self,
        hook: "PluginHook",
        handler: Callable[..., Any],
    ) -> None:
        hook_key = str(hook.value) if hasattr(hook, "value") else str(hook)
        if hook_key not in self._manager._hooks:
            self._manager._hooks[hook_key] = []
        self._manager._hooks[hook_key].append(handler)

    def register_http_handler(
        self,
        method: str,
        path: str,
        handler: Callable[..., Any],
    ) -> None:
        from clara_core.plugins.types import HttpRoute
        route = HttpRoute(method=method, path=path, handler=handler)
        self._manager._http_routes.append(route)

    def register_http_route(self, route: "HttpRoute") -> None:
        self._manager._http_routes.append(route)

    def register_gateway_method(
        self,
        method_name: str,
        handler: Callable[..., Any],
    ) -> None:
        self._manager._gateway_methods[method_name] = handler

    def register_cli(self, register: Callable[..., Any]) -> None:
        self._manager._cli_registrations.append(register)

    def register_service(self, service_key: str, service: Any) -> None:
        self._manager._services[service_key] = service
        state = self._manager._plugins.get(self._plugin_id)
        if state:
            state.services[service_key] = service

    def get_service(self, service_key: str) -> Any:
        return self._manager._services.get(service_key)

    def register_provider(self, provider_type: str, provider: Any) -> None:
        if provider_type not in self._manager._providers:
            self._manager._providers[provider_type] = {}
        self._manager._providers[provider_type][self._plugin_id] = provider

    def register_command(
        self,
        name: str,
        handler: Callable[..., Any],
        description: str = "",
    ) -> None:
        self._manager._commands[name] = handler

    def register_model_provider(self, provider_id: str, provider: Any) -> None:
        self._manager._model_providers[provider_id] = provider


def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager instance."""
    return PluginManager.get_instance()
