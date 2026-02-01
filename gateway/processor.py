"""Message processor for the Clara Gateway.

Handles:
- Event conversion and routing through the cognition pipeline
- Tool call execution and pipeline re-entry
- Response streaming to WebSocket adapters

The processor converts gateway MessageRequests into CognitionEvents,
processes them through the unified pipeline, and streams results back
to connected adapters. Tool calls are executed via ToolExecutor and
re-entered into the pipeline as TOOL_RESULT events with rate limiting.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

from config.logging import get_logger
from clara_core.cognition import (
    CognitionEvent,
    CognitionPipeline,
    EventMetadata,
    EventType,
    PipelineConfig,
    RateLimitConfig,
    RejectedEvent,
    ResponseCompleteEvent,
    TextChunkEvent,
    ToolCallEvent,
)
from gateway.protocol import (
    ErrorMessage,
    MessageRequest,
    ResponseChunk,
    ResponseEnd,
    ResponseStart,
    ToolResult,
    ToolStart,
)
from gateway.tool_executor import ToolExecutor

if TYPE_CHECKING:
    from websockets.server import WebSocketServerProtocol

    from gateway.server import GatewayServer

logger = get_logger("gateway.processor")

# Thread pool for blocking operations
BLOCKING_EXECUTOR = ThreadPoolExecutor(
    max_workers=int(os.getenv("GATEWAY_IO_THREADS", "20")),
    thread_name_prefix="gateway-io-",
)

# Configuration from environment
MAX_TOOL_CALLS_PER_REQUEST = int(os.getenv("GATEWAY_MAX_TOOL_CALLS_PER_REQUEST", "10"))
MAX_TOOL_CALLS_PER_MINUTE = int(os.getenv("GATEWAY_MAX_TOOL_CALLS_PER_MINUTE", "20"))


class MessageProcessor:
    """Processes messages through the Clara cognition pipeline.

    This is the core processing engine that:
    1. Converts MessageRequests to CognitionEvents
    2. Routes events through the cognition pipeline
    3. Executes tool calls and re-enters pipeline with results
    4. Streams responses back to adapters
    """

    def __init__(self) -> None:
        """Initialize the processor."""
        self._initialized = False
        self._memory_manager: Any = None
        self._tool_executor: ToolExecutor | None = None
        self._pipeline: CognitionPipeline | None = None

    async def initialize(self) -> None:
        """Initialize the processor with required resources.

        Called once during gateway startup.
        """
        if self._initialized:
            return

        # Initialize memory manager
        await self._init_memory_manager()

        # Initialize tool executor
        self._tool_executor = ToolExecutor()
        await self._tool_executor.initialize()

        # Initialize cognition pipeline
        self._pipeline = CognitionPipeline(
            config=PipelineConfig(
                router_config=RateLimitConfig(
                    max_tool_calls_per_request=MAX_TOOL_CALLS_PER_REQUEST,
                    max_tool_calls_per_minute=MAX_TOOL_CALLS_PER_MINUTE,
                ),
            ),
            memory_manager=self._memory_manager,
        )

        self._initialized = True
        logger.info(
            "MessageProcessor initialized (rate limits: %d/request, %d/min)",
            MAX_TOOL_CALLS_PER_REQUEST,
            MAX_TOOL_CALLS_PER_MINUTE,
        )

    async def _init_memory_manager(self) -> None:
        """Initialize the memory manager."""
        try:
            from clara_core import MemoryManager, init_platform, make_llm

            init_platform()
            self._memory_manager = MemoryManager(make_llm)
            logger.info("MemoryManager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize MemoryManager: {e}")
            raise

    async def process(
        self,
        request: MessageRequest,
        websocket: WebSocketServerProtocol,
        server: GatewayServer,
    ) -> None:
        """Process a message request and stream the response.

        Converts the MessageRequest to a CognitionEvent, processes through
        the pipeline, executes any tool calls, and streams responses back.

        Args:
            request: The incoming message request
            websocket: WebSocket to send responses to
            server: The gateway server instance
        """
        response_id = f"resp-{uuid.uuid4().hex[:8]}"
        request_id = request.id

        logger.info(
            "Processing message %s from %s: %s...",
            request_id,
            request.user.id,
            request.content[:50],
        )

        # Send response start
        await self._send(
            websocket,
            ResponseStart(
                id=response_id,
                request_id=request_id,
                model_tier=request.tier_override,
            ),
        )

        try:
            # Convert MessageRequest to CognitionEvent
            event = self._request_to_event(request)

            # Get available tools
            tools = self._tool_executor.get_all_tools() if self._tool_executor else []

            # Process through pipeline with tool execution loop
            full_text, tool_count, files = await self._process_with_tools(
                event=event,
                tools=tools,
                request_id=request_id,
                response_id=response_id,
                websocket=websocket,
            )

            # Send response end
            await self._send(
                websocket,
                ResponseEnd(
                    id=response_id,
                    request_id=request_id,
                    full_text=full_text,
                    files=files,
                    tool_count=tool_count,
                ),
            )

            logger.info(
                "Completed response %s (%d chars, %d tools)",
                response_id,
                len(full_text),
                tool_count,
            )

        except asyncio.CancelledError:
            logger.info(f"Processing cancelled for {request_id}")
            raise
        except Exception as e:
            logger.exception(f"Error processing {request_id}: {e}")
            await self._send(
                websocket,
                ErrorMessage(
                    request_id=request_id,
                    code="processing_error",
                    message=str(e),
                    recoverable=True,
                ),
            )
            raise
        finally:
            # Clean up rate limit state for this request
            if self._pipeline:
                self._pipeline.reset_request(request_id)

    async def _process_with_tools(
        self,
        event: CognitionEvent,
        tools: list[dict[str, Any]],
        request_id: str,
        response_id: str,
        websocket: WebSocketServerProtocol,
    ) -> tuple[str, int, list[str]]:
        """Process an event through the pipeline, handling tool calls.

        Executes the pipeline, and for each ToolCallEvent:
        1. Executes the tool via ToolExecutor
        2. Creates a TOOL_RESULT event
        3. Re-enters the pipeline

        This continues until ResponseCompleteEvent or RejectedEvent.

        Args:
            event: The cognition event to process
            tools: Available tool definitions
            request_id: Request ID for tracking
            response_id: Response ID for protocol messages
            websocket: WebSocket for sending updates

        Returns:
            Tuple of (full_text, tool_count, files_to_send)
        """
        if not self._pipeline or not self._tool_executor:
            raise RuntimeError("Processor not initialized")

        full_text = ""
        tool_count = 0
        files_to_send: list[str] = []
        current_event = event

        while True:
            async for pipeline_event in self._pipeline.process(current_event, tools):
                if isinstance(pipeline_event, TextChunkEvent):
                    # Stream text chunk to adapter
                    full_text += pipeline_event.text
                    await self._send(
                        websocket,
                        ResponseChunk(
                            id=response_id,
                            request_id=request_id,
                            chunk=pipeline_event.text,
                            accumulated=full_text,
                        ),
                    )

                elif isinstance(pipeline_event, ToolCallEvent):
                    # Execute tool and prepare re-entry
                    tool_count += 1

                    # Send tool start notification
                    await self._send(
                        websocket,
                        ToolStart(
                            id=response_id,
                            request_id=request_id,
                            tool_name=pipeline_event.tool_name,
                            step=tool_count,
                            emoji=self._get_tool_emoji(pipeline_event.tool_name),
                        ),
                    )

                    # Execute the tool
                    result = await self._tool_executor.execute(
                        tool_name=pipeline_event.tool_name,
                        arguments=pipeline_event.tool_args,
                        user_id=event.user_id,
                        channel_id=event.metadata.channel_id,
                        files_to_send=files_to_send,
                    )

                    # Determine success
                    success = not result.startswith("Error:")

                    # Send tool result notification
                    await self._send(
                        websocket,
                        ToolResult(
                            id=response_id,
                            request_id=request_id,
                            tool_name=pipeline_event.tool_name,
                            success=success,
                            output_preview=result[:200] if len(result) > 200 else result,
                        ),
                    )

                    # Create TOOL_RESULT event for pipeline re-entry
                    current_event = CognitionEvent(
                        type=EventType.TOOL_RESULT,
                        payload={
                            "result": result,
                            "tool_name": pipeline_event.tool_name,
                            "call_id": pipeline_event.call_id,
                            "success": success,
                        },
                        metadata=EventMetadata(
                            request_id=request_id,  # Same request_id for rate limiting
                            user_id=event.user_id,
                            channel_id=event.metadata.channel_id,
                            source=event.metadata.source,
                        ),
                    )
                    # Break inner loop to re-enter pipeline
                    break

                elif isinstance(pipeline_event, RejectedEvent):
                    # Rate limited or skipped
                    if pipeline_event.rate_limit_info:
                        logger.warning(
                            "Rate limited: %s (%s: %d/%d)",
                            pipeline_event.reason,
                            pipeline_event.rate_limit_info.get("type"),
                            pipeline_event.rate_limit_info.get("current"),
                            pipeline_event.rate_limit_info.get("max"),
                        )
                        # Send error about rate limit
                        await self._send(
                            websocket,
                            ErrorMessage(
                                request_id=request_id,
                                code="rate_limited",
                                message=pipeline_event.reason,
                                recoverable=False,
                            ),
                        )
                    else:
                        logger.debug("Event rejected: %s", pipeline_event.reason)
                    return full_text or "Request was rate limited.", tool_count, files_to_send

                elif isinstance(pipeline_event, ResponseCompleteEvent):
                    # Done processing
                    full_text = pipeline_event.full_text
                    return full_text, tool_count, files_to_send

            else:
                # Inner loop completed without break (no tool calls)
                # This means we got ResponseCompleteEvent and already returned
                return full_text, tool_count, files_to_send

    def _request_to_event(self, request: MessageRequest) -> CognitionEvent:
        """Convert a MessageRequest to a CognitionEvent.

        Args:
            request: The gateway message request

        Returns:
            CognitionEvent for pipeline processing
        """
        is_dm = request.channel.type == "dm"

        # Build user content with display name prefix for non-DMs
        content = request.content
        if not is_dm and request.user.display_name:
            content = f"[{request.user.display_name}]: {request.content}"

        # Build payload
        payload = {
            "content": content,
            "raw_content": request.content,
            "attachments": [att.model_dump() for att in request.attachments],
            "reply_chain": request.reply_chain,
            "tier_override": request.tier_override,
            "platform_metadata": request.metadata,
        }

        # Build metadata
        metadata = EventMetadata(
            request_id=request.id,
            user_id=request.user.id,
            channel_id=request.channel.id,
            source=request.metadata.get("platform", "gateway"),
        )

        # Add gateway context to payload
        payload["gateway_context"] = self._build_gateway_context(request, is_dm)
        payload["is_dm"] = is_dm
        payload["has_mention"] = True  # Gateway messages are always directed at Clara
        payload["user_name"] = request.user.name
        payload["user_display_name"] = request.user.display_name

        return CognitionEvent(
            type=EventType.MESSAGE,
            payload=payload,
            metadata=metadata,
        )

    def _build_gateway_context(self, request: MessageRequest, is_dm: bool) -> str:
        """Build gateway-specific context information.

        Args:
            request: The message request
            is_dm: Whether this is a DM

        Returns:
            Context string
        """
        from datetime import UTC, datetime

        parts = [
            "## Current Context",
            f"- Current time: {datetime.now(UTC).strftime('%A, %B %d, %Y at %H:%M UTC')}",
            f"- Platform: {request.metadata.get('platform', 'unknown')}",
        ]

        if is_dm:
            parts.append("- Conversation: Private DM")
        else:
            if request.channel.name:
                parts.append(f"- Channel: #{request.channel.name}")
            if request.channel.guild_name:
                parts.append(f"- Server: {request.channel.guild_name}")

        parts.append(f"- User: {request.user.display_name or request.user.name or request.user.id}")

        return "\n".join(parts)

    def _get_tool_emoji(self, tool_name: str) -> str:
        """Get emoji for a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Emoji string
        """
        tool_emojis = {
            "execute_python": "snake",
            "install_package": "package",
            "read_file": "open_book",
            "write_file": "floppy_disk",
            "list_files": "file_folder",
            "run_shell": "computer",
            "unzip_file": "open_file_folder",
            "web_search": "mag",
            "run_claude_code": "robot",
            "save_to_local": "floppy_disk",
            "list_local_files": "file_folder",
            "read_local_file": "open_book",
            "delete_local_file": "wastebasket",
            "download_from_sandbox": "arrow_down",
            "upload_to_sandbox": "arrow_up",
            "send_local_file": "outbox_tray",
            "create_file_attachment": "paperclip",
            "search_chat_history": "mag",
            "get_chat_history": "scroll",
            "check_email": "postbox",
            "search_email": "mag",
            "send_email": "outbox_tray",
            "github_get_me": "octopus",
            "github_search_repositories": "mag",
            "github_get_repository": "open_file_folder",
            "github_list_issues": "clipboard",
            "github_get_issue": "bookmark",
            "github_create_issue": "heavy_plus_sign",
            "github_list_pull_requests": "twisted_rightwards_arrows",
            "github_get_pull_request": "bookmark_tabs",
            "github_create_pull_request": "twisted_rightwards_arrows",
            "github_list_commits": "memo",
            "github_get_file_contents": "page_facing_up",
            "github_search_code": "mag",
            "github_list_workflow_runs": "gear",
            "github_run_workflow": "arrow_forward",
        }
        return tool_emojis.get(tool_name, "gear")

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
        import websockets

        try:
            await websocket.send(message.model_dump_json())
        except websockets.ConnectionClosed:
            logger.debug("Connection closed while sending")
            raise asyncio.CancelledError("Connection closed")
