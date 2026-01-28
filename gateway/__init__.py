"""Clara Gateway - WebSocket gateway for platform adapters.

The gateway provides a central message processing hub that platform adapters
connect to via WebSocket. This allows:
- Platform-agnostic message processing
- Horizontal scaling of adapters
- Stateless reconnection
- Unified tool execution
- Event-driven hooks for automation
- Built-in task scheduler (cron/interval)
"""

from gateway.events import (
    Event,
    EventEmitter,
    EventType,
    emit,
    get_event_emitter,
    on,
    off,
)
from gateway.hooks import (
    Hook,
    HookManager,
    HookResult,
    HookType,
    get_hook_manager,
    hook,
)
from gateway.llm_orchestrator import LLMOrchestrator
from gateway.processor import MessageProcessor
from gateway.protocol import (
    GatewayMessage,
    MessageRequest,
    MessageType,
    NodeInfo,
    RegisteredMessage,
    RegisterMessage,
    ResponseChunk,
    ResponseEnd,
    ResponseStart,
    ToolResult,
    ToolStart,
)
from gateway.router import MessageRouter
from gateway.scheduler import (
    CronParser,
    ScheduledTask,
    Scheduler,
    TaskResult,
    TaskType,
    get_scheduler,
    scheduled,
)
from gateway.server import GatewayServer
from gateway.session import NodeRegistry, SessionManager
from gateway.tool_executor import ToolExecutor

__all__ = [
    # Events
    "Event",
    "EventEmitter",
    "EventType",
    "emit",
    "get_event_emitter",
    "on",
    "off",
    # Hooks
    "Hook",
    "HookManager",
    "HookResult",
    "HookType",
    "get_hook_manager",
    "hook",
    # Scheduler
    "CronParser",
    "ScheduledTask",
    "Scheduler",
    "TaskResult",
    "TaskType",
    "get_scheduler",
    "scheduled",
    # Protocol
    "GatewayMessage",
    "MessageType",
    "RegisterMessage",
    "RegisteredMessage",
    "MessageRequest",
    "ResponseStart",
    "ResponseChunk",
    "ToolStart",
    "ToolResult",
    "ResponseEnd",
    "NodeInfo",
    # Server
    "GatewayServer",
    # Session
    "NodeRegistry",
    "SessionManager",
    # Router
    "MessageRouter",
    # Processor
    "MessageProcessor",
    # LLM
    "LLMOrchestrator",
    # Tools
    "ToolExecutor",
]
