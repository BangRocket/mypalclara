"""Base gateway client for platform adapters.

Provides common WebSocket communication with the Clara Gateway.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable

import websockets
from websockets.client import WebSocketClientProtocol

from config.logging import get_logger
from gateway.protocol import (
    CancelMessage,
    ChannelInfo,
    GatewayMessage,
    MessageRequest,
    MessageType,
    PingMessage,
    RegisterMessage,
    UserInfo,
    parse_gateway_message,
)

logger = get_logger("adapters.base")


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

    async def start(self) -> None:
        """Start the client (connect and begin processing)."""
        if not await self.connect():
            raise RuntimeError("Failed to connect to gateway")

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
        except websockets.ConnectionClosed:
            logger.info("Gateway connection closed")
            self._connected = False
            # Trigger reconnection if enabled
            if self._running and self.auto_reconnect:
                self._reconnect_task = asyncio.create_task(self._reconnect())
                await self._reconnect_task
                if self._connected:
                    # Resume receive loop after reconnection
                    await self._receive_loop()
        except Exception as e:
            logger.exception(f"Receive loop error: {e}")
            self._connected = False
            # Trigger reconnection if enabled
            if self._running and self.auto_reconnect:
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

        request = MessageRequest(
            id=f"msg-{uuid.uuid4().hex[:8]}",
            user=user,
            channel=channel,
            content=content,
            attachments=[],  # TODO: Convert attachments
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
        """Handle response start from gateway."""
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
        """Handle error from gateway."""
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

    @property
    def is_connected(self) -> bool:
        """Check if connected to gateway."""
        return self._connected
