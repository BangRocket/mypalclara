"""WebSocket server for the Clara Gateway.

Accepts connections from platform adapters and routes messages
to the processing pipeline.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any

import websockets
from websockets.server import WebSocketServerProtocol, serve

from config.logging import get_structured_logger
from gateway.rate_limiter import RateLimiter
from gateway.protocol import (
    CancelledMessage,
    CancelMessage,
    ErrorMessage,
    MessageRequest,
    MessageType,
    PingMessage,
    PongMessage,
    RegisteredMessage,
    RegisterMessage,
    StatusMessage,
    parse_adapter_message,
)
from gateway.router import MessageRouter
from gateway.session import NodeRegistry, SessionManager

if TYPE_CHECKING:
    pass

logger = get_structured_logger("gateway.server")


class GatewayServer:
    """WebSocket server that accepts adapter connections.

    Handles:
    - Adapter registration and heartbeats
    - Message routing to processor
    - Response streaming back to adapters
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 18789,
        secret: str | None = None,
    ) -> None:
        """Initialize the gateway server.

        Args:
            host: Bind address
            port: Port to listen on
            secret: Optional shared secret for authentication
        """
        self.host = host
        self.port = port
        self.secret = secret or os.getenv("CLARA_GATEWAY_SECRET")

        self.node_registry = NodeRegistry()
        self.session_manager = SessionManager(self.node_registry)
        self.router = MessageRouter()
        self.rate_limiter = RateLimiter()

        self._server: websockets.WebSocketServer | None = None
        self._cleanup_task: asyncio.Task | None = None
        self._started_at: datetime | None = None
        self._message_count = 0

        # Connection tracking
        self._active_connections = 0
        self._total_connections = 0

        # WebSocket resource limits (configurable via environment)
        self._ws_max_message_size = int(os.getenv("WS_MAX_MESSAGE_SIZE", 65536))  # 64KB
        self._ws_max_queue = int(os.getenv("WS_MAX_QUEUE", 16))
        self._ws_read_limit = int(os.getenv("WS_READ_LIMIT", 65536))  # 64KB
        self._ws_write_limit = int(os.getenv("WS_WRITE_LIMIT", 65536))  # 64KB

        # Processor will be set by gateway.main
        self._processor: Any = None

    def set_processor(self, processor: Any) -> None:
        """Set the message processor.

        Args:
            processor: MessageProcessor instance
        """
        self._processor = processor

    async def start(self) -> None:
        """Start the WebSocket server."""
        self._started_at = datetime.now()

        # Log resource limits
        logger.info(
            "websocket_resource_limits",
            max_message_size=self._ws_max_message_size,
            max_queue=self._ws_max_queue,
            read_limit=self._ws_read_limit,
            write_limit=self._ws_write_limit,
        )

        self._server = await serve(
            self._handle_connection,
            self.host,
            self.port,
            ping_interval=30,
            ping_timeout=10,
            max_size=self._ws_max_message_size,
            max_queue=self._ws_max_queue,
            read_limit=self._ws_read_limit,
            write_limit=self._ws_write_limit,
        )
        # Start rate limiter cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_rate_limits())
        logger.info(f"Gateway server started on ws://{self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the WebSocket server."""
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("Gateway server stopped")

    async def _cleanup_rate_limits(self) -> None:
        """Periodically clean up stale rate limit buckets."""
        while True:
            await asyncio.sleep(3600)  # Every hour
            removed = await self.rate_limiter.cleanup_stale()
            if removed > 0:
                logger.debug(f"Cleaned up {removed} stale rate limit buckets")

    async def _handle_connection(
        self,
        websocket: WebSocketServerProtocol,
    ) -> None:
        """Handle a new WebSocket connection.

        Args:
            websocket: The WebSocket connection
        """
        # Track connection
        self._active_connections += 1
        self._total_connections += 1
        logger.debug(
            "connection_opened",
            active_connections=self._active_connections,
            total_connections=self._total_connections,
        )

        node_id = None
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    parsed = parse_adapter_message(data)

                    if isinstance(parsed, RegisterMessage):
                        node_id = await self._handle_register(websocket, parsed)

                    elif isinstance(parsed, PingMessage):
                        await self._handle_ping(websocket)

                    elif isinstance(parsed, MessageRequest):
                        await self._handle_message_request(websocket, parsed)

                    elif isinstance(parsed, CancelMessage):
                        await self._handle_cancel(websocket, parsed)

                    elif isinstance(parsed, StatusMessage):
                        await self._handle_status_request(websocket)

                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON from client: {e}")
                    await self._send_error(websocket, None, "invalid_json", str(e))

                except ValueError as e:
                    logger.warning(f"Invalid message: {e}")
                    await self._send_error(websocket, None, "invalid_message", str(e))

                except Exception as e:
                    logger.exception(f"Error handling message: {e}")
                    await self._send_error(websocket, None, "internal_error", str(e))

        except websockets.ConnectionClosed:
            logger.debug("Connection closed")
        finally:
            # Track disconnection
            self._active_connections -= 1
            logger.debug(
                "connection_closed",
                active_connections=self._active_connections,
            )
            # Clean up on disconnect
            if node_id:
                await self.node_registry.unregister(websocket)

    async def _handle_register(
        self,
        websocket: WebSocketServerProtocol,
        msg: RegisterMessage,
    ) -> str:
        """Handle adapter registration.

        Args:
            websocket: The WebSocket connection
            msg: Registration message

        Returns:
            The registered node ID
        """
        session_id, is_reconnection = await self.node_registry.register(
            websocket=websocket,
            node_id=msg.node_id,
            platform=msg.platform,
            capabilities=msg.capabilities,
            metadata=msg.metadata,
        )

        response = RegisteredMessage(
            node_id=msg.node_id,
            session_id=session_id,
        )
        await self._send(websocket, response)

        action = "reconnected" if is_reconnection else "registered"
        logger.info(f"Node {msg.node_id} ({msg.platform}) {action}")

        return msg.node_id

    async def _handle_ping(self, websocket: WebSocketServerProtocol) -> None:
        """Handle ping from adapter."""
        await self.node_registry.update_ping(websocket)
        await self._send(websocket, PongMessage())

    async def _handle_message_request(
        self,
        websocket: WebSocketServerProtocol,
        msg: MessageRequest,
    ) -> None:
        """Handle a message processing request.

        Args:
            websocket: The WebSocket connection
            msg: The message request
        """
        self._message_count += 1

        # Get node info
        node = await self.node_registry.get_node_by_websocket(websocket)
        if not node:
            await self._send_error(websocket, msg.id, "not_registered", "Node not registered")
            return

        # Check rate limit
        allowed, retry_after = await self.rate_limiter.check_rate_limit(
            channel_id=msg.channel.id,
            user_id=msg.user.id,
        )

        # Log message request with context
        logger.info(
            "message_request",
            request_id=msg.id,
            user_id=msg.user.id,
            channel_id=msg.channel.id,
            rate_limited=not allowed,
        )

        if not allowed:
            await self._send_error(
                websocket,
                msg.id,
                "rate_limited",
                f"Rate limit exceeded. Retry after {retry_after:.1f}s",
                recoverable=True,
            )
            return

        # Determine if request is batchable (active mode, not DM/mention)
        is_batchable = msg.channel.type == "server" and not msg.metadata.get("is_mention", False)

        # Try to acquire channel
        acquired, position = await self.router.submit(
            request=msg,
            websocket=websocket,
            node_id=node.node_id,
            is_batchable=is_batchable,
        )

        if acquired:
            # Process immediately
            await self._process_request(websocket, node.node_id, msg)
        else:
            # Notify about queue position
            await self._send(
                websocket,
                StatusMessage(
                    active_requests=1,
                    queue_length=position,
                ),
            )

    async def _process_request(
        self,
        websocket: WebSocketServerProtocol,
        node_id: str,
        msg: MessageRequest,
    ) -> None:
        """Process a message request.

        Args:
            websocket: The WebSocket connection
            node_id: The adapter node ID
            msg: The message request
        """
        if not self._processor:
            logger.error("No processor configured")
            await self._send_error(websocket, msg.id, "no_processor", "Gateway not configured")
            await self.router.complete(msg.id)
            return

        # Create processing task
        task = asyncio.create_task(
            self._processor.process(
                request=msg,
                websocket=websocket,
                server=self,
            )
        )
        await self.router.register_task(msg.id, task)

        try:
            await task
        except asyncio.CancelledError:
            logger.info(f"Request {msg.id} was cancelled")
            await self._send(websocket, CancelledMessage(request_id=msg.id))
        except Exception as e:
            logger.exception(f"Error processing request {msg.id}: {e}")
            await self._send_error(websocket, msg.id, "processing_error", str(e))
        finally:
            # Complete and check for next
            next_request = await self.router.complete(msg.id)
            if next_request:
                # Process next queued request
                await self._process_request(
                    next_request.websocket,
                    next_request.node_id,
                    next_request.request,
                )

    async def _handle_cancel(
        self,
        websocket: WebSocketServerProtocol,
        msg: CancelMessage,
    ) -> None:
        """Handle cancel request.

        Args:
            websocket: The WebSocket connection
            msg: The cancel message
        """
        cancelled = await self.router.cancel(msg.request_id)
        if cancelled:
            await self._send(websocket, CancelledMessage(request_id=msg.request_id))
        else:
            await self._send_error(
                websocket,
                msg.request_id,
                "not_found",
                "Request not found or already completed",
            )

    async def _handle_status_request(
        self,
        websocket: WebSocketServerProtocol,
    ) -> None:
        """Handle status request."""
        router_stats = await self.router.get_stats()
        node_stats = await self.node_registry.get_stats()
        session_stats = await self.session_manager.get_stats()

        uptime = None
        if self._started_at:
            uptime = int((datetime.now() - self._started_at).total_seconds())

        await self._send(
            websocket,
            StatusMessage(
                active_requests=router_stats["active_channels"],
                queue_length=router_stats["total_queued"],
                uptime_seconds=uptime,
            ),
        )

    async def _send(
        self,
        websocket: WebSocketServerProtocol,
        message: Any,
    ) -> None:
        """Send a message to a WebSocket.

        Args:
            websocket: Target WebSocket
            message: Pydantic model to send
        """
        try:
            await websocket.send(message.model_dump_json())
        except websockets.ConnectionClosed:
            logger.debug("Connection closed while sending")

    async def _send_error(
        self,
        websocket: WebSocketServerProtocol,
        request_id: str | None,
        code: str,
        message: str,
        recoverable: bool = True,
    ) -> None:
        """Send an error message.

        Args:
            websocket: Target WebSocket
            request_id: Related request ID if any
            code: Error code
            message: Error message
            recoverable: Whether client can retry
        """
        error = ErrorMessage(
            request_id=request_id,
            code=code,
            message=message,
            recoverable=recoverable,
        )
        await self._send(websocket, error)

    async def broadcast_to_platform(
        self,
        platform: str,
        message: Any,
    ) -> int:
        """Broadcast a message to all nodes of a platform.

        Args:
            platform: Target platform name
            message: Pydantic model to send

        Returns:
            Number of nodes messaged
        """
        nodes = await self.node_registry.get_nodes_by_platform(platform)
        count = 0
        for node in nodes:
            try:
                await self._send(node.websocket, message)
                count += 1
            except Exception as e:
                logger.warning(f"Failed to send to node {node.node_id}: {e}")
        return count

    def get_stats(self) -> dict[str, Any]:
        """Get server statistics (sync version for monitoring)."""
        uptime = None
        if self._started_at:
            uptime = int((datetime.now() - self._started_at).total_seconds())

        return {
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "uptime_seconds": uptime,
            "message_count": self._message_count,
            "active_connections": self._active_connections,
            "total_connections": self._total_connections,
            "resource_limits": {
                "max_message_size": self._ws_max_message_size,
                "max_queue": self._ws_max_queue,
                "read_limit": self._ws_read_limit,
                "write_limit": self._ws_write_limit,
            },
        }
