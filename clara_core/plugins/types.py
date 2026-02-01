"""Plugin system types and interfaces.

Defines the ClaraPluginApi that plugins use to register functionality.
Follows OpenClaw's 13-method plugin API pattern.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Protocol

if TYPE_CHECKING:
    from clara_core.channels.types import ChannelPlugin


class PluginHook(str, Enum):
    """Lifecycle hooks that plugins can register.

    Matches OpenClaw's 13 hook types.
    """

    # Gateway lifecycle
    GATEWAY_START = "gateway:start"
    GATEWAY_STOP = "gateway:stop"

    # Channel lifecycle
    CHANNEL_START = "channel:start"
    CHANNEL_STOP = "channel:stop"

    # Message lifecycle
    MESSAGE_RECEIVED = "message:received"
    MESSAGE_SENT = "message:sent"
    MESSAGE_CANCELLED = "message:cancelled"

    # Agent lifecycle
    AGENT_START = "agent:start"
    AGENT_END = "agent:end"

    # Tool lifecycle
    TOOL_START = "tool:start"
    TOOL_END = "tool:end"
    TOOL_ERROR = "tool:error"

    # Configuration
    CONFIG_RELOAD = "config:reload"

    # Session
    SESSION_START = "session:start"
    SESSION_END = "session:end"
    SESSION_TIMEOUT = "session:timeout"

    # Scheduler
    SCHEDULER_TASK_RUN = "scheduler:task_run"
    SCHEDULER_TASK_ERROR = "scheduler:task_error"


@dataclass
class ToolDefinition:
    """Definition of an agent tool.

    Tools are functions that the AI agent can call during message processing.
    """

    # Tool name (unique identifier)
    name: str

    # Human-readable description
    description: str

    # JSON Schema for parameters
    parameters: dict[str, Any]

    # The handler function
    handler: Callable[..., Any]

    # Whether this tool requires confirmation
    requires_confirmation: bool = False

    # Category for grouping
    category: str = "general"

    # Whether this tool can modify state
    is_mutating: bool = False


# Type alias for tool factory functions
ToolFactory = Callable[[], list[ToolDefinition]]


@dataclass
class HttpRoute:
    """HTTP route registration."""

    method: str  # GET, POST, PUT, DELETE, etc.
    path: str  # URL path pattern
    handler: Callable[..., Any]  # Request handler
    description: str = ""
    auth_required: bool = True


@dataclass
class PluginRuntime:
    """Runtime information provided to plugins.

    Gives plugins access to core services and configuration.
    """

    # Plugin identifier
    plugin_id: str

    # Plugin version
    version: str

    # Configuration directory
    config_dir: str

    # Data directory for plugin storage
    data_dir: str

    # Whether running in debug mode
    debug: bool = False

    # Gateway URL if available
    gateway_url: str | None = None


class ClaraPluginApi(Protocol):
    """Plugin API interface.

    Provides methods for plugins to register functionality with Clara.
    Matches OpenClaw's 13-method plugin API.
    """

    @property
    def runtime(self) -> PluginRuntime:
        """Get plugin runtime information."""
        ...

    # Channel registration
    def register_channel(
        self,
        plugin: "ChannelPlugin[Any]",
    ) -> None:
        """Register a channel plugin."""
        ...

    # Tool registration
    def register_tool(
        self,
        tool: ToolDefinition | ToolFactory,
    ) -> None:
        """Register an agent tool or tool factory."""
        ...

    # Hook registration
    def register_hook(
        self,
        hook: PluginHook,
        handler: Callable[..., Any],
    ) -> None:
        """Register a lifecycle hook handler."""
        ...

    # HTTP route registration
    def register_http_handler(
        self,
        method: str,
        path: str,
        handler: Callable[..., Any],
    ) -> None:
        """Register an HTTP route handler."""
        ...

    def register_http_route(
        self,
        route: HttpRoute,
    ) -> None:
        """Register an HTTP route."""
        ...

    # Gateway method registration
    def register_gateway_method(
        self,
        method_name: str,
        handler: Callable[..., Any],
    ) -> None:
        """Register a gateway RPC method."""
        ...

    # CLI command registration
    def register_cli(
        self,
        register: Callable[..., Any],
    ) -> None:
        """Register CLI commands."""
        ...

    # Service registration
    def register_service(
        self,
        service_key: str,
        service: Any,
    ) -> None:
        """Register a shared service."""
        ...

    def get_service(
        self,
        service_key: str,
    ) -> Any:
        """Get a registered service."""
        ...

    # Provider registration (for LLM providers, etc.)
    def register_provider(
        self,
        provider_type: str,
        provider: Any,
    ) -> None:
        """Register a provider (LLM, storage, etc.)."""
        ...

    # Command registration (user-facing commands)
    def register_command(
        self,
        name: str,
        handler: Callable[..., Any],
        description: str = "",
    ) -> None:
        """Register a user-facing command."""
        ...

    # Model provider registration
    def register_model_provider(
        self,
        provider_id: str,
        provider: Any,
    ) -> None:
        """Register an LLM model provider."""
        ...


@dataclass
class ClaraPlugin:
    """Plugin metadata and entry point.

    Plugins implement this to register with Clara.
    """

    # Plugin identifier (unique)
    id: str

    # Human-readable name
    name: str

    # Version string
    version: str = "1.0.0"

    # Description
    description: str = ""

    # Author
    author: str | None = None

    # Dependencies (other plugin IDs)
    dependencies: list[str] = field(default_factory=list)

    # Entry point function
    # Called with ClaraPluginApi to register functionality
    register: Callable[[ClaraPluginApi], None] | None = None

    # Optional async initialization
    init: Callable[[], Any] | None = None

    # Optional cleanup
    cleanup: Callable[[], Any] | None = None
