"""Base gateway client for platform adapters.

Provides common WebSocket communication with the Clara Gateway.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

import websockets
from websockets.client import WebSocketClientProtocol

from adapters.protocols import CAPABILITY_PROTOCOLS
from config.logging import get_logger
from mypalclara.gateway.protocol import (
    AttachmentInfo,
    CancelMessage,
    ChannelInfo,
    GatewayMessage,
    MCPEnableRequest,
    MCPEnableResponse,
    MCPInstallRequest,
    MCPInstallResponse,
    MCPListRequest,
    MCPListResponse,
    MCPRestartRequest,
    MCPRestartResponse,
    MCPStatusRequest,
    MCPStatusResponse,
    MCPUninstallRequest,
    MCPUninstallResponse,
    MessageRequest,
    MessageType,
    PingMessage,
    RegisterMessage,
    UserInfo,
    parse_gateway_message,
)

logger = get_logger("adapters.base")


# =============================================================================
# Error Recovery System
# =============================================================================


class ErrorCategory(Enum):
    """Categories for error recovery decisions."""

    TRANSIENT = "transient"  # Network timeout, rate limit → retry with backoff
    CONNECTION = "connection"  # WebSocket closed, auth fail → reconnect
    CONFIGURATION = "configuration"  # Missing env, bad creds → stop, alert
    FATAL = "fatal"  # Unrecoverable → stop, alert


def classify_error(error: Exception) -> ErrorCategory:
    """Classify an exception for recovery decisions.

    Args:
        error: The exception to classify

    Returns:
        ErrorCategory indicating how to handle the error
    """
    error_str = str(error).lower()
    error_type = type(error).__name__

    # Configuration errors - stop and alert
    if any(
        term in error_str
        for term in [
            "missing env",
            "invalid api key",
            "authentication failed",
            "unauthorized",
            "403",
            "invalid token",
            "permission denied",
        ]
    ):
        return ErrorCategory.CONFIGURATION

    # Connection errors - reconnect with backoff
    if any(
        term in error_type
        for term in [
            "ConnectionClosed",
            "ConnectionRefused",
            "ConnectionReset",
            "WebSocketException",
        ]
    ) or any(
        term in error_str
        for term in [
            "connection closed",
            "connection refused",
            "connection reset",
            "websocket",
            "disconnect",
        ]
    ):
        return ErrorCategory.CONNECTION

    # Transient errors - retry with backoff
    if any(
        term in error_str
        for term in [
            "timeout",
            "rate limit",
            "429",
            "503",
            "502",
            "504",
            "temporary",
            "try again",
            "overloaded",
        ]
    ):
        return ErrorCategory.TRANSIENT

    # TimeoutError is transient
    if isinstance(error, (asyncio.TimeoutError, TimeoutError)):
        return ErrorCategory.TRANSIENT

    # OSError with errno is usually transient network issues
    if isinstance(error, OSError):
        return ErrorCategory.TRANSIENT

    # Unknown errors are treated as fatal to avoid infinite retry loops
    return ErrorCategory.FATAL


# =============================================================================
# Health Check System
# =============================================================================


class HealthStatus(Enum):
    """Health status levels for adapters."""

    HEALTHY = "healthy"  # Fully operational
    DEGRADED = "degraded"  # Functional but with issues
    UNHEALTHY = "unhealthy"  # Not functional


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    status: HealthStatus
    latency_ms: float | None = None
    details: dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=datetime.now)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "details": self.details,
            "checked_at": self.checked_at.isoformat(),
            "error": self.error,
        }


def get_capabilities(adapter_class: type) -> list[str]:
    """Get the capabilities supported by an adapter class.

    Checks which protocol interfaces the adapter class implements
    and returns the corresponding capability names.

    Args:
        adapter_class: The adapter class to check

    Returns:
        List of capability names (e.g., ["streaming", "attachments", "reactions"])
    """
    capabilities = []
    for capability_name, protocol_class in CAPABILITY_PROTOCOLS.items():
        if isinstance(adapter_class, type):
            # Check if class implements the protocol
            try:
                if issubclass(adapter_class, protocol_class):
                    capabilities.append(capability_name)
            except TypeError:
                # Protocol check may fail for non-classes
                pass
        else:
            # Check instance
            if isinstance(adapter_class, protocol_class):
                capabilities.append(capability_name)
    return capabilities


class GatewayClient(ABC):
    """Base class for gateway-connected adapters.

    Handles:
    - WebSocket connection to gateway
    - Registration and heartbeats
    - Message sending and response handling
    - Automatic reconnection with session preservation
    """

    def __init__(
        self,
        platform: str,
        capabilities: list[str] | None = None,
        gateway_url: str | None = None,
        auto_reconnect: bool = True,
        reconnect_delay: float = 1.0,
        max_reconnect_delay: float = 60.0,
    ) -> None:
        """Initialize the gateway client.

        Args:
            platform: Platform name (discord, cli, slack)
            capabilities: Supported features
            gateway_url: WebSocket URL of the gateway
            auto_reconnect: Whether to auto-reconnect on disconnect
            reconnect_delay: Initial reconnect delay in seconds
            max_reconnect_delay: Maximum reconnect delay (exponential backoff cap)
        """
        self.platform = platform
        self.capabilities = capabilities or ["streaming"]
        self.gateway_url = gateway_url or os.getenv("CLARA_GATEWAY_URL", "ws://127.0.0.1:18789")

        self.node_id = f"{platform}-{uuid.uuid4().hex[:8]}"
        self.session_id: str | None = None

        # Reconnection settings
        self.auto_reconnect = auto_reconnect
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay
        self._current_reconnect_delay = reconnect_delay
        self._reconnect_attempts = 0

        self._ws: WebSocketClientProtocol | None = None
        self._connected = False
        self._running = False
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._pending_requests: dict[str, asyncio.Future[None]] = {}
        self._response_handlers: dict[str, Callable[[GatewayMessage], Any]] = {}

        # MCP request tracking
        self._pending_mcp_requests: dict[str, asyncio.Future[GatewayMessage]] = {}

    async def connect(self) -> bool:
        """Connect to the gateway.

        Returns:
            True if connected successfully
        """
        try:
            logger.info(f"Connecting to gateway at {self.gateway_url}")
            self._ws = await websockets.connect(
                self.gateway_url,
                ping_interval=None,  # We handle our own heartbeats
            )

            # Register with gateway
            register = RegisterMessage(
                node_id=self.node_id,
                platform=self.platform,
                capabilities=self.capabilities,
            )
            await self._ws.send(register.model_dump_json())

            # Wait for registration response
            response = await asyncio.wait_for(self._ws.recv(), timeout=10.0)
            data = json.loads(response)

            if data.get("type") == MessageType.REGISTERED:
                self.session_id = data.get("session_id")
                self._connected = True
                logger.info(f"Registered as {self.node_id} with session {self.session_id}")
                return True
            else:
                logger.error(f"Unexpected registration response: {data}")
                return False

        except Exception as e:
            logger.error(f"Failed to connect to gateway: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from the gateway."""
        self._running = False
        self._connected = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self._reconnect_task:
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            await self._ws.close()
            self._ws = None

        logger.info("Disconnected from gateway")

    async def _reconnect(self) -> None:
        """Attempt to reconnect to the gateway with exponential backoff."""
        while self._running and self.auto_reconnect:
            try:
                logger.info(
                    f"Reconnecting in {self._current_reconnect_delay:.1f}s "
                    f"(attempt {self._reconnect_attempts + 1})..."
                )
                await asyncio.sleep(self._current_reconnect_delay)

                if await self.connect():
                    # Reset backoff on successful connection
                    self._current_reconnect_delay = self.reconnect_delay
                    self._reconnect_attempts = 0
                    logger.info("Reconnected successfully")
                    await self.on_reconnect()
                    return
                else:
                    # Exponential backoff
                    self._reconnect_attempts += 1
                    self._current_reconnect_delay = min(
                        self._current_reconnect_delay * 2,
                        self.max_reconnect_delay,
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Reconnection error: {e}")
                self._reconnect_attempts += 1
                self._current_reconnect_delay = min(
                    self._current_reconnect_delay * 2,
                    self.max_reconnect_delay,
                )

    async def on_reconnect(self) -> None:
        """Called after successful reconnection.

        Override to restore state after reconnect.
        """
        pass

    async def start(self, max_initial_attempts: int = 10) -> None:
        """Start the client (connect and begin processing).

        Args:
            max_initial_attempts: Maximum connection attempts on startup.
                Set to 0 for infinite retries. Default is 10.
        """
        # Retry initial connection with exponential backoff
        # This handles cases where the gateway isn't ready yet (e.g., Docker startup)
        attempt = 0
        while True:
            if await self.connect():
                break

            attempt += 1
            if max_initial_attempts > 0 and attempt >= max_initial_attempts:
                raise RuntimeError(f"Failed to connect to gateway after {attempt} attempts")

            delay = min(self._current_reconnect_delay, self.max_reconnect_delay)
            logger.info(
                f"Gateway not ready, retrying in {delay:.1f}s " f"(attempt {attempt}/{max_initial_attempts or '∞'})..."
            )
            await asyncio.sleep(delay)

            # Exponential backoff
            self._current_reconnect_delay = min(
                self._current_reconnect_delay * 2,
                self.max_reconnect_delay,
            )

        # Reset backoff after successful connection
        self._current_reconnect_delay = self.reconnect_delay
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # Start message receive loop
        await self._receive_loop()

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats to the gateway."""
        while self._running and self._connected:
            try:
                if self._ws:
                    await self._ws.send(PingMessage().model_dump_json())
                await asyncio.sleep(25)  # Heartbeat interval
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Heartbeat error: {e}")

    async def _receive_loop(self) -> None:
        """Receive and process messages from the gateway."""
        if not self._ws:
            return

        try:
            async for message in self._ws:
                try:
                    data = json.loads(message)
                    parsed = parse_gateway_message(data)
                    await self._handle_message(parsed)
                except Exception as e:
                    logger.warning(f"Error handling message: {e}")
        except websockets.ConnectionClosed as e:
            logger.info("Gateway connection closed")
            self._connected = False
            # Use error classification for reconnection decision
            if self._running and self._should_reconnect(e):
                self._reconnect_task = asyncio.create_task(self._reconnect())
                await self._reconnect_task
                if self._connected:
                    # Resume receive loop after reconnection
                    await self._receive_loop()
        except Exception as e:
            logger.exception(f"Receive loop error: {e}")
            self._connected = False
            # Use error classification for reconnection decision
            if self._running and self._should_reconnect(e):
                self._reconnect_task = asyncio.create_task(self._reconnect())
                await self._reconnect_task
                if self._connected:
                    await self._receive_loop()

    async def _handle_message(self, message: GatewayMessage) -> None:
        """Handle a message from the gateway.

        Args:
            message: The parsed gateway message
        """
        msg_type = message.type

        if msg_type == MessageType.PONG:
            # Heartbeat acknowledged
            pass
        elif msg_type == MessageType.RESPONSE_START:
            await self.on_response_start(message)
        elif msg_type == MessageType.RESPONSE_CHUNK:
            await self.on_response_chunk(message)
        elif msg_type == MessageType.RESPONSE_END:
            await self.on_response_end(message)
        elif msg_type == MessageType.TOOL_START:
            await self.on_tool_start(message)
        elif msg_type == MessageType.TOOL_RESULT:
            await self.on_tool_result(message)
        elif msg_type == MessageType.ERROR:
            await self.on_error(message)
        elif msg_type == MessageType.CANCELLED:
            await self.on_cancelled(message)
        elif msg_type == MessageType.STATUS:
            await self.on_status(message)
        elif msg_type == MessageType.PROACTIVE_MESSAGE:
            await self.on_proactive_message(message)
        # MCP Response types
        elif msg_type in (
            MessageType.MCP_LIST_RESPONSE,
            MessageType.MCP_INSTALL_RESPONSE,
            MessageType.MCP_UNINSTALL_RESPONSE,
            MessageType.MCP_STATUS_RESPONSE,
            MessageType.MCP_RESTART_RESPONSE,
            MessageType.MCP_ENABLE_RESPONSE,
        ):
            await self._handle_mcp_response(message)
        else:
            logger.debug(f"Unhandled message type: {msg_type}")

    async def send_message(
        self,
        user: UserInfo,
        channel: ChannelInfo,
        content: str,
        attachments: list[dict[str, Any]] | None = None,
        reply_chain: list[dict[str, Any]] | None = None,
        tier_override: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Send a message request to the gateway.

        Args:
            user: User information
            channel: Channel information
            content: Message content
            attachments: Optional attachments
            reply_chain: Optional conversation history
            tier_override: Optional model tier
            metadata: Optional platform-specific metadata

        Returns:
            The request ID
        """
        if not self._ws or not self._connected:
            raise RuntimeError("Not connected to gateway")

        # Convert attachment dicts to AttachmentInfo objects
        attachment_infos = []
        if attachments:
            for att in attachments:
                attachment_infos.append(AttachmentInfo(**att))

        request = MessageRequest(
            id=f"msg-{uuid.uuid4().hex[:8]}",
            user=user,
            channel=channel,
            content=content,
            attachments=attachment_infos,
            reply_chain=reply_chain or [],
            tier_override=tier_override,
            metadata=metadata or {"platform": self.platform},
        )

        await self._ws.send(request.model_dump_json())
        return request.id

    async def cancel_request(self, request_id: str, reason: str | None = None) -> None:
        """Cancel an in-flight request.

        Args:
            request_id: The request to cancel
            reason: Optional cancellation reason
        """
        if not self._ws or not self._connected:
            return

        cancel = CancelMessage(request_id=request_id, reason=reason)
        await self._ws.send(cancel.model_dump_json())

    # Abstract methods for subclasses to implement
    @abstractmethod
    async def on_response_start(self, message: Any) -> None:
        """Handle response start from mypalclara.gateway."""
        ...

    @abstractmethod
    async def on_response_chunk(self, message: Any) -> None:
        """Handle streaming response chunk."""
        ...

    @abstractmethod
    async def on_response_end(self, message: Any) -> None:
        """Handle response completion."""
        ...

    @abstractmethod
    async def on_tool_start(self, message: Any) -> None:
        """Handle tool execution start."""
        ...

    @abstractmethod
    async def on_tool_result(self, message: Any) -> None:
        """Handle tool execution result."""
        ...

    async def on_error(self, message: Any) -> None:
        """Handle error from mypalclara.gateway."""
        logger.error(f"Gateway error: {message.code}: {message.message}")

    async def on_cancelled(self, message: Any) -> None:
        """Handle request cancellation."""
        logger.info(f"Request {message.request_id} cancelled")

    async def on_status(self, message: Any) -> None:
        """Handle status update."""
        logger.debug(f"Queue status: {message.queue_length} queued")

    async def on_proactive_message(self, message: Any) -> None:
        """Handle proactive message from ORS."""
        logger.info(f"Proactive message for {message.user.id}: {message.content[:50]}")

    # =========================================================================
    # MCP Management Methods
    # =========================================================================

    async def _handle_mcp_response(self, message: GatewayMessage) -> None:
        """Handle MCP response messages by resolving pending futures.

        Args:
            message: The MCP response message
        """
        request_id = getattr(message, "request_id", None)
        if request_id and request_id in self._pending_mcp_requests:
            future = self._pending_mcp_requests.pop(request_id)
            if not future.done():
                future.set_result(message)
        else:
            logger.warning(f"Received MCP response for unknown request: {request_id}")

    async def _send_mcp_request(
        self,
        request: Any,
        timeout: float = 30.0,
    ) -> GatewayMessage:
        """Send an MCP request and wait for response.

        Args:
            request: The MCP request message
            timeout: Timeout in seconds

        Returns:
            The MCP response message

        Raises:
            RuntimeError: If not connected to gateway
            asyncio.TimeoutError: If response times out
        """
        if not self._ws or not self._connected:
            raise RuntimeError("Not connected to gateway")

        request_id = request.request_id
        future: asyncio.Future[GatewayMessage] = asyncio.get_event_loop().create_future()
        self._pending_mcp_requests[request_id] = future

        try:
            await self._ws.send(request.model_dump_json())
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_mcp_requests.pop(request_id, None)
            raise
        except Exception:
            self._pending_mcp_requests.pop(request_id, None)
            raise

    async def mcp_list(self, timeout: float = 30.0) -> MCPListResponse:
        """List all MCP servers.

        Args:
            timeout: Request timeout in seconds

        Returns:
            MCPListResponse with server list
        """
        import uuid

        request = MCPListRequest(request_id=f"mcp-{uuid.uuid4().hex[:8]}")
        response = await self._send_mcp_request(request, timeout)
        return response  # type: ignore

    async def mcp_install(
        self,
        source: str,
        name: str | None = None,
        requested_by: str | None = None,
        timeout: float = 120.0,
    ) -> MCPInstallResponse:
        """Install an MCP server.

        Args:
            source: Server source (npm package, smithery:name, github URL)
            name: Custom name for the server
            requested_by: User ID who requested installation
            timeout: Request timeout in seconds (longer for install)

        Returns:
            MCPInstallResponse with installation result
        """
        import uuid

        request = MCPInstallRequest(
            request_id=f"mcp-{uuid.uuid4().hex[:8]}",
            source=source,
            name=name,
            requested_by=requested_by,
        )
        response = await self._send_mcp_request(request, timeout)
        return response  # type: ignore

    async def mcp_uninstall(
        self,
        server_name: str,
        timeout: float = 30.0,
    ) -> MCPUninstallResponse:
        """Uninstall an MCP server.

        Args:
            server_name: Name of server to uninstall
            timeout: Request timeout in seconds

        Returns:
            MCPUninstallResponse with result
        """
        import uuid

        request = MCPUninstallRequest(
            request_id=f"mcp-{uuid.uuid4().hex[:8]}",
            server_name=server_name,
        )
        response = await self._send_mcp_request(request, timeout)
        return response  # type: ignore

    async def mcp_status(
        self,
        server_name: str | None = None,
        timeout: float = 30.0,
    ) -> MCPStatusResponse:
        """Get MCP server status.

        Args:
            server_name: Specific server name (None for overall status)
            timeout: Request timeout in seconds

        Returns:
            MCPStatusResponse with status info
        """
        import uuid

        request = MCPStatusRequest(
            request_id=f"mcp-{uuid.uuid4().hex[:8]}",
            server_name=server_name,
        )
        response = await self._send_mcp_request(request, timeout)
        return response  # type: ignore

    async def mcp_restart(
        self,
        server_name: str,
        timeout: float = 60.0,
    ) -> MCPRestartResponse:
        """Restart an MCP server.

        Args:
            server_name: Name of server to restart
            timeout: Request timeout in seconds

        Returns:
            MCPRestartResponse with result
        """
        import uuid

        request = MCPRestartRequest(
            request_id=f"mcp-{uuid.uuid4().hex[:8]}",
            server_name=server_name,
        )
        response = await self._send_mcp_request(request, timeout)
        return response  # type: ignore

    async def mcp_enable(
        self,
        server_name: str,
        enabled: bool,
        timeout: float = 30.0,
    ) -> MCPEnableResponse:
        """Enable or disable an MCP server.

        Args:
            server_name: Name of server to enable/disable
            enabled: True to enable, False to disable
            timeout: Request timeout in seconds

        Returns:
            MCPEnableResponse with result
        """
        import uuid

        request = MCPEnableRequest(
            request_id=f"mcp-{uuid.uuid4().hex[:8]}",
            server_name=server_name,
            enabled=enabled,
        )
        response = await self._send_mcp_request(request, timeout)
        return response  # type: ignore

    # =========================================================================
    # Error Recovery and Health Check
    # =========================================================================

    def _should_reconnect(self, error: Exception) -> bool:
        """Determine if we should attempt reconnection based on error type.

        Args:
            error: The exception that caused disconnection

        Returns:
            True if reconnection should be attempted, False otherwise
        """
        if not self.auto_reconnect:
            return False

        category = classify_error(error)

        if category in (ErrorCategory.TRANSIENT, ErrorCategory.CONNECTION):
            return True
        elif category == ErrorCategory.CONFIGURATION:
            logger.error(f"Configuration error, not reconnecting: {error}")
            return False
        elif category == ErrorCategory.FATAL:
            logger.error(f"Fatal error, not reconnecting: {error}")
            return False

        return False

    async def health_check(self) -> HealthCheckResult:
        """Check the health of the gateway connection.

        Override in subclasses for platform-specific health checks.

        Returns:
            HealthCheckResult with connection status
        """
        start = time.time()

        # Check basic connection state
        if not self._ws or not self._connected:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                error="Not connected to gateway",
                details={
                    "connected": False,
                    "node_id": self.node_id,
                    "platform": self.platform,
                },
            )

        # Try to send a ping and measure latency
        try:
            await self._ws.send(PingMessage().model_dump_json())
            latency = (time.time() - start) * 1000  # Convert to ms

            # Determine health based on latency
            if latency < 100:
                status = HealthStatus.HEALTHY
            elif latency < 500:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.DEGRADED

            return HealthCheckResult(
                status=status,
                latency_ms=latency,
                details={
                    "connected": True,
                    "node_id": self.node_id,
                    "session_id": self.session_id,
                    "platform": self.platform,
                    "reconnect_attempts": self._reconnect_attempts,
                },
            )

        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                latency_ms=(time.time() - start) * 1000,
                error=str(e),
                details={
                    "connected": self._connected,
                    "node_id": self.node_id,
                    "platform": self.platform,
                    "error_category": classify_error(e).value,
                },
            )

    @property
    def is_connected(self) -> bool:
        """Check if connected to gateway."""
        return self._connected
