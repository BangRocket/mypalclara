"""Message processor for the Clara Gateway.

Handles:
- Context building (memory fetch, history)
- LLM orchestration with tool calling
- Response streaming
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

from config.logging import get_structured_logger
from gateway.llm_orchestrator import LLMOrchestrator
from gateway.protocol import (
    MessageRequest,
    ResponseChunk,
    ResponseEnd,
    ResponseStart,
    ToolResult,
    ToolStart,
)
from gateway.tool_executor import ToolExecutor

if TYPE_CHECKING:
    from websockets.asyncio.server import ServerConnection

    from gateway.server import GatewayServer

logger = get_structured_logger("gateway.processor")

# Thread pool for blocking operations
BLOCKING_EXECUTOR = ThreadPoolExecutor(
    max_workers=int(os.getenv("GATEWAY_IO_THREADS", "20")),
    thread_name_prefix="gateway-io-",
)


class MessageProcessor:
    """Processes messages through the Clara pipeline.

    This is the core processing engine that:
    1. Fetches context (memories, history)
    2. Builds prompts
    3. Calls LLM with tool support
    4. Streams responses back to adapters
    """

    def __init__(self) -> None:
        """Initialize the processor."""
        self._initialized = False
        self._memory_manager: Any = None
        self._tool_executor: ToolExecutor | None = None
        self._llm_orchestrator: LLMOrchestrator | None = None

    async def initialize(self) -> None:
        """Initialize the processor with required resources.

        Called once during gateway startup.
        """
        if self._initialized:
            return

        # Initialize tool executor
        self._tool_executor = ToolExecutor()
        await self._tool_executor.initialize()

        # Initialize LLM orchestrator
        self._llm_orchestrator = LLMOrchestrator()
        await self._llm_orchestrator.initialize(self._tool_executor)

        # Initialize memory manager
        await self._init_memory_manager()

        self._initialized = True
        logger.info("MessageProcessor initialized")

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
        websocket: ServerConnection,
        server: GatewayServer,
    ) -> None:
        """Process a message request and stream the response.

        Args:
            request: The incoming message request
            websocket: WebSocket to send responses to
            server: The gateway server instance
        """
        start_time = time.time()
        response_id = f"resp-{uuid.uuid4().hex[:8]}"

        # Bind context for structured logging
        log = logger.bind(
            request_id=request.id,
            user_id=request.user.id,
            channel_id=request.channel.id,
            platform=request.metadata.get("platform", "unknown"),
        )

        log.info("message_received", content_length=len(request.content))

        # Send response start
        await self._send(
            websocket,
            ResponseStart(
                id=response_id,
                request_id=request.id,
                model_tier=request.tier_override,
            ),
        )

        try:
            # Build context and process
            context = await self._build_context(request)
            tools = self._tool_executor.get_all_tools() if self._tool_executor else []

            # Generate response with tools
            full_text = ""
            tool_count = 0
            files: list[str] = []

            async for event in self._llm_orchestrator.generate_with_tools(
                messages=context["messages"],
                tools=tools,
                user_id=request.user.id,
                request_id=request.id,
                tier=request.tier_override,
                websocket=websocket,
            ):
                event_type = event.get("type")

                if event_type == "tool_start":
                    await self._send(
                        websocket,
                        ToolStart(
                            id=response_id,
                            tool_name=event["tool_name"],
                            step=event["step"],
                            emoji=self._get_tool_emoji(event["tool_name"]),
                        ),
                    )

                elif event_type == "tool_result":
                    await self._send(
                        websocket,
                        ToolResult(
                            id=response_id,
                            tool_name=event["tool_name"],
                            success=event["success"],
                            output_preview=event.get("output_preview"),
                        ),
                    )

                elif event_type == "chunk":
                    chunk_text = event["text"]
                    full_text += chunk_text
                    await self._send(
                        websocket,
                        ResponseChunk(
                            id=response_id,
                            chunk=chunk_text,
                            accumulated=full_text,
                        ),
                    )

                elif event_type == "complete":
                    full_text = event["text"]
                    tool_count = event.get("tool_count", 0)
                    files = event.get("files", [])

            # Store in memory
            await self._store_exchange(request, full_text, context)

            # Send response end
            await self._send(
                websocket,
                ResponseEnd(
                    id=response_id,
                    full_text=full_text,
                    files=files,
                    tool_count=tool_count,
                ),
            )

            duration_ms = int((time.time() - start_time) * 1000)
            log.info(
                "message_complete",
                response_length=len(full_text),
                tool_count=tool_count,
                duration_ms=duration_ms,
            )

        except asyncio.CancelledError:
            log.info("processing_cancelled")
            raise
        except Exception as e:
            log.exception("processing_error", error=str(e))
            raise

    async def _build_context(self, request: MessageRequest) -> dict[str, Any]:
        """Build context for the LLM including memories and prompt.

        Args:
            request: The message request

        Returns:
            Context dict with messages, user_id, project_id, etc.
        """
        loop = asyncio.get_event_loop()
        user_id = request.user.id
        channel_id = request.channel.id
        is_dm = request.channel.type == "dm"

        # Prepare user content
        user_content = request.content
        if not is_dm and request.user.display_name:
            user_content = f"[{request.user.display_name}]: {request.content}"

        # Fetch memories from mem0
        user_mems, proj_mems, graph_relations = await loop.run_in_executor(
            BLOCKING_EXECUTOR,
            lambda: self._memory_manager.fetch_mem0_context(
                user_id,
                None,  # No project for now
                user_content,
                participants=[],
                is_dm=is_dm,
            ),
        )

        # Build base prompt with Clara's persona
        messages = self._memory_manager.build_prompt(
            user_mems,
            proj_mems,
            None,  # session_summary
            [],  # recent_msgs
            user_content,
            graph_relations=graph_relations,
        )

        # Add gateway context
        gateway_context = self._build_gateway_context(request, is_dm)
        messages.insert(1, {"role": "system", "content": gateway_context})

        # Add reply chain if present
        if request.reply_chain:
            chain_messages = []
            for msg in request.reply_chain:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                chain_messages.append({"role": role, "content": content})

            # Insert before the current message
            messages = messages[:-1] + chain_messages + [messages[-1]]

        return {
            "messages": messages,
            "user_id": user_id,
            "channel_id": channel_id,
            "is_dm": is_dm,
            "user_mems": user_mems,
            "proj_mems": proj_mems,
        }

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

    async def _store_exchange(
        self,
        request: MessageRequest,
        response: str,
        context: dict[str, Any],
    ) -> None:
        """Store the exchange in Clara's memory.

        Args:
            request: The original request
            response: Clara's response
            context: The context dict
        """
        if not response:
            return

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                BLOCKING_EXECUTOR,
                lambda: self._memory_manager.add_to_memory(
                    context["user_id"],
                    request.content,
                    response,
                    is_dm=context["is_dm"],
                ),
            )
        except Exception as e:
            logger.warning(f"Failed to store exchange: {e}")

    def _get_tool_emoji(self, tool_name: str) -> str:
        """Get emoji for a tool.

        Args:
            tool_name: Name of the tool

        Returns:
            Emoji string
        """
        tool_emojis = {
            "execute_python": "🐍",
            "install_package": "📦",
            "read_file": "📖",
            "write_file": "💾",
            "list_files": "📁",
            "run_shell": "💻",
            "unzip_file": "📂",
            "web_search": "🔍",
            "run_claude_code": "🤖",
            "save_to_local": "💾",
            "list_local_files": "📁",
            "read_local_file": "📖",
            "delete_local_file": "🗑️",
            "download_from_sandbox": "⬇️",
            "upload_to_sandbox": "⬆️",
            "send_local_file": "📤",
            "create_file_attachment": "📎",
            "search_chat_history": "🔎",
            "get_chat_history": "📜",
            "check_email": "📬",
            "search_email": "🔎",
            "send_email": "📤",
            "github_get_me": "🐙",
            "github_search_repositories": "🔍",
            "github_get_repository": "📂",
            "github_list_issues": "📋",
            "github_get_issue": "🔖",
            "github_create_issue": "➕",
            "github_list_pull_requests": "🔀",
            "github_get_pull_request": "📑",
            "github_create_pull_request": "🔀",
            "github_list_commits": "📝",
            "github_get_file_contents": "📄",
            "github_search_code": "🔎",
            "github_list_workflow_runs": "⚙️",
            "github_run_workflow": "▶️",
        }
        return tool_emojis.get(tool_name, "⚙️")

    async def _send(
        self,
        websocket: ServerConnection,
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
