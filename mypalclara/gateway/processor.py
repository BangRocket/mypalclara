"""Message processor for the Clara Gateway.

Handles:
- Context building (memory fetch, history)
- LLM orchestration with tool calling
- Response streaming
- Message persistence
"""

from __future__ import annotations

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

from clara_core.config import get_settings
from clara_core.llm.messages import AssistantMessage, SystemMessage, UserMessage
from clara_core.llm.messages import Message as LLMMessage
from config.logging import get_logger
from db import SessionLocal
from db.models import Message
from db.models import Session as DBSession
from mypalclara.gateway.channel_summaries import ChannelSummaryManager, get_summary_manager
from mypalclara.gateway.llm_orchestrator import LLMOrchestrator
from mypalclara.gateway.protocol import (
    MessageRequest,
    ResponseChunk,
    ResponseEnd,
    ResponseStart,
    ToolResult,
    ToolStart,
)
from mypalclara.gateway.tool_executor import ToolExecutor

if TYPE_CHECKING:
    from websockets.server import WebSocketServerProtocol

    from mypalclara.gateway.server import GatewayServer

logger = get_logger("gateway.processor")

# Thread pool for blocking operations
BLOCKING_EXECUTOR = ThreadPoolExecutor(
    max_workers=get_settings().gateway.io_threads,
    thread_name_prefix="gateway-io-",
)

# Auto-tier configuration
AUTO_TIER_ENABLED = get_settings().llm.auto_tier.enabled

# Tier classification prompt (uses fast model to decide)
TIER_CLASSIFICATION_PROMPT = """Analyze this message and recent context to determine complexity level.

Message: {message}

Recent context (last 4 messages):
{context}

Classify as:
- LOW: Simple greetings, quick facts, basic questions, casual chat, yes/no answers
- MID: Moderate tasks, explanations, summaries, most coding questions, follow-up discussions
- HIGH: Complex reasoning, long-form writing, difficult coding, multi-step analysis, research

IMPORTANT: Consider the conversation context. A short reply like "yes" or "ok" in an ongoing complex discussion should remain at the same tier as the discussion.

Respond with only one word: LOW, MID, or HIGH"""


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
        self._summary_manager: ChannelSummaryManager | None = None
        self._background_tasks: set[asyncio.Task] = set()

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

        # Initialize channel summary manager
        self._summary_manager = get_summary_manager()
        await self._summary_manager.initialize()

        self._initialized = True
        logger.info("MessageProcessor initialized")

    async def shutdown(self) -> None:
        """Shut down the processor: wait for background tasks, then close MCP servers."""
        if self._background_tasks:
            logger.info(f"Waiting for {len(self._background_tasks)} background memory tasks...")
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            logger.info("All background memory tasks completed")

        # Shut down MCP servers after background tasks (which may use MCP tools)
        if self._tool_executor:
            await self._tool_executor.shutdown()

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

    def _get_or_create_db_session(
        self,
        user_id: str,
        channel_id: str,
        is_dm: bool = False,
    ) -> DBSession:
        """Get or create a database session for conversation persistence.

        Args:
            user_id: The user's ID
            channel_id: The channel/context ID
            is_dm: Whether this is a DM

        Returns:
            Database Session object
        """
        from db.models import Project

        db = SessionLocal()
        try:
            # Build context_id from channel
            context_id = f"dm-{user_id}" if is_dm else f"channel-{channel_id}"

            # Get or create default project for this user
            project = db.query(Project).filter_by(owner_id=user_id).first()
            if not project:
                project_name = get_settings().default_project
                project = Project(owner_id=user_id, name=project_name)
                db.add(project)
                db.commit()
                db.refresh(project)

            # Find existing active session
            session = (
                db.query(DBSession)
                .filter(
                    DBSession.user_id == user_id,
                    DBSession.context_id == context_id,
                    DBSession.project_id == project.id,
                    DBSession.archived != "true",
                )
                .order_by(DBSession.last_activity_at.desc())
                .first()
            )

            if session:
                # Update activity timestamp
                from db.models import utcnow

                session.last_activity_at = utcnow()
                db.commit()
                db.refresh(session)
                db.expunge(session)
                return session

            # Find most recent prior session for continuity
            prev_session = (
                db.query(DBSession)
                .filter(
                    DBSession.user_id == user_id,
                    DBSession.context_id == context_id,
                    DBSession.project_id == project.id,
                )
                .order_by(DBSession.last_activity_at.desc())
                .first()
            )

            # Create new session linked to previous
            session = DBSession(
                user_id=user_id,
                context_id=context_id,
                project_id=project.id,
                previous_session_id=prev_session.id if prev_session else None,
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            db.expunge(session)
            logger.debug(f"Created DB session {session.id} for {user_id}/{context_id}")
            return session

        finally:
            db.close()

    def _get_previous_session_summary(self, db_session: DBSession) -> str | None:
        """Walk the previous_session_id chain to find a session summary.

        Checks up to 3 prior sessions for a non-empty summary.

        Args:
            db_session: Current database session

        Returns:
            Summary string from a previous session, or None
        """
        db = SessionLocal()
        try:
            current = db_session
            for _ in range(3):
                prev_id = current.previous_session_id
                if not prev_id:
                    return None
                prev = db.query(DBSession).filter(DBSession.id == prev_id).first()
                if not prev:
                    return None
                if prev.session_summary:
                    return prev.session_summary
                current = prev
            return None
        finally:
            db.close()

    def _store_message(
        self,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
    ) -> None:
        """Store a message in the database.

        Args:
            session_id: Database session ID
            user_id: User ID
            role: Message role ('user' or 'assistant')
            content: Message content
        """
        db = SessionLocal()
        try:
            msg = Message(
                session_id=session_id,
                user_id=user_id,
                role=role,
                content=content,
            )
            db.add(msg)
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to store message: {e}")
            db.rollback()
        finally:
            db.close()

    def _get_recent_messages(
        self,
        session_id: str,
        limit: int = 15,
    ) -> list[Message]:
        """Fetch recent messages from a database session.

        Args:
            session_id: Database session ID
            limit: Maximum messages to fetch

        Returns:
            List of Message objects in chronological order
        """
        db = SessionLocal()
        try:
            messages = (
                db.query(Message)
                .filter(Message.session_id == session_id)
                .order_by(Message.created_at.desc())
                .limit(limit)
                .all()
            )
            # Return in chronological order
            return list(reversed(messages))
        except Exception as e:
            logger.warning(f"Failed to fetch messages: {e}")
            return []
        finally:
            db.close()

    async def process(
        self,
        request: MessageRequest,
        websocket: WebSocketServerProtocol,
        server: GatewayServer,
    ) -> None:
        """Process a message request and stream the response.

        Args:
            request: The incoming message request
            websocket: WebSocket to send responses to
            server: The gateway server instance
        """
        response_id = f"resp-{uuid.uuid4().hex[:8]}"

        logger.info(f"Processing message {request.id} from {request.user.id}: " f"{request.content[:50]}...")

        # Determine model tier
        tier = request.tier_override
        if not tier and AUTO_TIER_ENABLED:
            tier = await self._classify_tier(request)
            logger.info(f"Auto-tier classification: {tier}")

        # Send response start
        await self._send(
            websocket,
            ResponseStart(
                id=response_id,
                request_id=request.id,
                model_tier=tier,
            ),
        )

        try:
            # Build context and process
            context = await self._build_context(request)

            # Get adapter capabilities for tool filtering
            adapter_capabilities: list[str] = []
            node = await server.node_registry.get_node_by_websocket(websocket)
            if node:
                adapter_capabilities = node.capabilities

            tools = (
                self._tool_executor.get_all_tools(adapter_capabilities=adapter_capabilities)
                if self._tool_executor
                else []
            )

            # Extract images from attachments
            images = [att for att in request.attachments if att.type == "image"]

            # Generate response with tools
            full_text = ""
            tool_count = 0
            files: list[str] = []

            async for event in self._llm_orchestrator.generate_with_tools(
                messages=context["messages"],
                tools=tools,
                user_id=request.user.id,
                request_id=request.id,
                tier=tier,
                websocket=websocket,
                images=images if images else None,
            ):
                event_type = event.get("type")

                if event_type == "tool_start":
                    await self._send(
                        websocket,
                        ToolStart(
                            id=response_id,
                            request_id=request.id,
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
                            request_id=request.id,
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
                            request_id=request.id,
                            chunk=chunk_text,
                            accumulated=full_text,
                        ),
                    )

                elif event_type == "complete":
                    full_text = event["text"]
                    tool_count = event.get("tool_count", 0)
                    files = event.get("files", [])

            # Store messages in database (fast, must complete before ResponseEnd)
            await self._store_messages_db(request, full_text, context)

            # Convert file paths to FileData with content
            file_data_list = await self._prepare_file_data(files)

            # Send response end immediately — don't wait for memory ops
            await self._send(
                websocket,
                ResponseEnd(
                    id=response_id,
                    request_id=request.id,
                    full_text=full_text,
                    files=files,  # Keep for backwards compatibility
                    file_data=file_data_list,
                    tool_count=tool_count,
                ),
            )

            logger.info(f"Completed response {response_id} ({len(full_text)} chars, {tool_count} tools)")

            # Memory extraction, vector/graph saves, and FSRS promotion
            # run in background so the user isn't blocked
            task = asyncio.create_task(self._background_memory_ops(request, full_text, context, response_id))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

        except asyncio.CancelledError:
            logger.info(f"Processing cancelled for {request.id}")
            raise
        except Exception as e:
            logger.exception(f"Error processing {request.id}: {e}")
            raise

    def _resolve_canonical_user_ids(self, prefixed_user_id: str) -> list[str]:
        """Resolve a prefixed user_id to all linked user_ids via CanonicalUser.

        If the user has linked multiple platforms (e.g., discord-123 and teams-456),
        this returns ALL prefixed IDs so memory queries span platforms.

        Args:
            prefixed_user_id: The prefixed user ID (e.g., 'discord-123')

        Returns:
            List of all prefixed user_ids for this canonical user,
            or [prefixed_user_id] if no canonical user found.
        """
        try:
            from db.models import PlatformLink

            db = SessionLocal()
            try:
                link = db.query(PlatformLink).filter(PlatformLink.prefixed_user_id == prefixed_user_id).first()
                if not link:
                    return [prefixed_user_id]

                all_links = (
                    db.query(PlatformLink.prefixed_user_id)
                    .filter(PlatformLink.canonical_user_id == link.canonical_user_id)
                    .all()
                )
                return [row[0] for row in all_links]
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"Canonical user resolution failed for {prefixed_user_id}: {e}")
            return [prefixed_user_id]

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

        # Get or create database session for persistence
        db_session = await loop.run_in_executor(
            BLOCKING_EXECUTOR,
            lambda: self._get_or_create_db_session(user_id, channel_id, is_dm),
        )

        # Fetch recent messages from database
        recent_msgs = await loop.run_in_executor(
            BLOCKING_EXECUTOR,
            lambda: self._get_recent_messages(db_session.id),
        )

        # Prepare user content with text file attachments
        user_content = request.content
        text_attachments = self._format_text_attachments(request.attachments)
        if text_attachments:
            if user_content:
                user_content = f"{user_content}\n\n{text_attachments}"
            else:
                user_content = text_attachments

        # Guard against empty user_content (e.g. file-only messages with no text)
        if not user_content or not user_content.strip():
            if request.attachments:
                filenames = ", ".join(att.filename for att in request.attachments if att.filename)
                user_content = f"[User sent file(s): {filenames}]" if filenames else "[User sent an attachment]"
            else:
                user_content = "[Empty message]"

        if not is_dm and request.user.display_name:
            user_content = f"[{request.user.display_name}]: {user_content}"

        # Extract participants from reply chain
        participants = self._extract_participants(request)

        # Fetch memories from mem0
        user_mems, proj_mems, graph_relations = await loop.run_in_executor(
            BLOCKING_EXECUTOR,
            lambda: self._memory_manager.fetch_mem0_context(
                user_id,
                None,  # No project for now
                user_content,
                participants=participants,
                is_dm=is_dm,
            ),
        )

        # Fetch emotional context (last 3 sessions)
        emotional_context = None
        try:
            emotional_context = await loop.run_in_executor(
                BLOCKING_EXECUTOR,
                lambda: self._memory_manager.fetch_emotional_context(user_id, limit=3),
            )
        except Exception as e:
            logger.debug(f"Could not fetch emotional context: {e}")

        # Fetch recurring topics (2+ mentions in 14 days)
        recurring_topics = None
        try:
            recurring_topics = await loop.run_in_executor(
                BLOCKING_EXECUTOR,
                lambda: self._memory_manager.fetch_recurring_topics(user_id, min_mentions=2, lookback_days=14),
            )
        except Exception as e:
            logger.debug(f"Could not fetch recurring topics: {e}")

        # Check intentions for this message
        fired_intentions = []
        try:
            intention_context = {
                "channel_name": request.channel.name or "",
                "is_dm": is_dm,
            }
            fired_intentions = await loop.run_in_executor(
                BLOCKING_EXECUTOR,
                lambda: self._memory_manager.check_intentions(user_id, user_content, intention_context),
            )
            if fired_intentions:
                logger.info(f"Fired {len(fired_intentions)} intentions for {user_id}")
        except Exception as e:
            logger.debug(f"Could not check intentions: {e}")

        # Get session summary if available, falling back to previous session's
        session_summary = db_session.session_summary if db_session else None
        if not session_summary and db_session:
            session_summary = await loop.run_in_executor(
                BLOCKING_EXECUTOR,
                lambda: self._get_previous_session_summary(db_session),
            )

        # Build base prompt with Clara's persona
        messages = self._memory_manager.build_prompt(
            user_mems,
            proj_mems,
            session_summary,
            recent_msgs,
            user_content,
            graph_relations=graph_relations,
            emotional_context=emotional_context,
            recurring_topics=recurring_topics,
        )

        # Add gateway context
        gateway_context = self._build_gateway_context(request, is_dm, participants)
        messages.insert(1, SystemMessage(content=gateway_context))

        # Add fired intentions as reminders
        if fired_intentions:
            intention_text = self._memory_manager.format_intentions_for_prompt(fired_intentions)
            if intention_text:
                messages.insert(2, SystemMessage(content=intention_text))

        # Add reply chain if present (skip empty messages)
        if request.reply_chain:
            chain_messages: list[LLMMessage] = []
            for msg in request.reply_chain:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if not content or not content.strip():
                    continue
                if role == "assistant":
                    chain_messages.append(AssistantMessage(content=content))
                else:
                    chain_messages.append(UserMessage(content=content))

            # Insert before the current message
            messages = messages[:-1] + chain_messages + [messages[-1]]

        # Resolve canonical user for cross-platform queries
        all_user_ids = await loop.run_in_executor(
            BLOCKING_EXECUTOR,
            lambda: self._resolve_canonical_user_ids(user_id),
        )

        return {
            "messages": messages,
            "user_id": user_id,
            "all_user_ids": all_user_ids,
            "channel_id": channel_id,
            "is_dm": is_dm,
            "user_mems": user_mems,
            "proj_mems": proj_mems,
            "participants": participants,
            "db_session_id": db_session.id if db_session else None,
            "user_content": user_content,
            "fired_intentions": fired_intentions,
        }

    def _format_text_attachments(self, attachments: list) -> str:
        """Format text file attachments for inclusion in user content.

        Args:
            attachments: List of AttachmentInfo objects

        Returns:
            Formatted string with file contents
        """
        if not attachments:
            return ""

        text_parts = []
        for att in attachments:
            if att.type == "text" and att.content:
                text_parts.append(
                    f"--- Attached file: {att.filename} ---\n{att.content}\n--- End of {att.filename} ---"
                )
            elif att.type == "file":
                # Non-extracted file — include metadata so LLM knows it exists
                size_str = f"{att.size} bytes" if att.size else "unknown size"
                media = att.media_type or "unknown type"
                text_parts.append(f"[Attached file: {att.filename} ({media}, {size_str}) - content not extracted]")

        return "\n\n".join(text_parts)

    def _extract_participants(self, request: MessageRequest) -> list[dict[str, str]]:
        """Extract participant info from reply chain for cross-user memory.

        Args:
            request: The message request

        Returns:
            List of participant dicts with id and name
        """
        participants = []
        seen_ids = set()

        # Add current user
        if request.user.id not in seen_ids:
            participants.append(
                {
                    "id": request.user.id,
                    "name": request.user.display_name or request.user.name,
                }
            )
            seen_ids.add(request.user.id)

        # Extract from reply chain
        if request.reply_chain:
            for msg in request.reply_chain:
                # Reply chain messages might have user info in metadata
                user_id = msg.get("user_id")
                user_name = msg.get("user_name")
                if user_id and user_id not in seen_ids:
                    participants.append({"id": user_id, "name": user_name or user_id})
                    seen_ids.add(user_id)

        return participants

    def _build_gateway_context(
        self,
        request: MessageRequest,
        is_dm: bool,
        participants: list[dict[str, str]] | None = None,
    ) -> str:
        """Build gateway-specific context information.

        Args:
            request: The message request
            is_dm: Whether this is a DM
            participants: List of participants in the conversation

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

        # Add participant context for group conversations
        if participants and len(participants) > 1:
            other_participants = [p["name"] for p in participants if p["id"] != request.user.id]
            if other_participants:
                parts.append(f"- Other participants: {', '.join(other_participants)}")

        # Add attachment info
        image_count = sum(1 for att in request.attachments if att.type == "image")
        text_count = sum(1 for att in request.attachments if att.type == "text")
        file_count = sum(1 for att in request.attachments if att.type == "file")

        if image_count:
            parts.append(f"- Images attached: {image_count}")
        if text_count:
            parts.append(f"- Text files attached: {text_count}")
        if file_count:
            parts.append(f"- Other files attached: {file_count}")

        # Voice conversation context
        if request.metadata.get("source") == "voice":
            parts.append("")
            parts.append("## Voice Conversation")
            parts.append(
                "You are in a live voice conversation. The user is speaking through a microphone"
                " — their messages are speech-to-text transcriptions. Your response will be read"
                " aloud by text-to-speech."
            )
            parts.append("")
            parts.append("Guidelines:")
            parts.append("- Keep responses concise and conversational — spoken language, not written")
            parts.append("- No markdown formatting, bullet lists, tables, or code blocks")
            parts.append("- No URLs or links")
            parts.append("- Use contractions and natural speech patterns")
            parts.append("- Shorter sentences — long compound sentences are hard to follow when spoken")
            parts.append(
                "- If the user's message seems garbled, they may have been misheard"
                " — ask for clarification rather than guessing"
            )
            parts.append("- For code or technical content, offer to type it out in the text channel instead")
            parts.append("- Brief is better — a 2-sentence answer often beats a 5-paragraph one")

        return "\n".join(parts)

    async def _prepare_file_data(self, file_paths: list[str]) -> list[dict[str, str]]:
        """Read files and prepare FileData for sending over WebSocket.

        Args:
            file_paths: List of local file paths

        Returns:
            List of FileData dicts with filename, content_base64, media_type
        """
        import base64
        import mimetypes
        from pathlib import Path

        file_data_list = []

        for path_str in file_paths:
            path = Path(path_str)
            if not path.exists():
                logger.warning(f"[file_data] File not found: {path}")
                continue

            try:
                # Read file content
                content = path.read_bytes()
                content_b64 = base64.b64encode(content).decode("utf-8")

                # Determine MIME type
                mime_type, _ = mimetypes.guess_type(path.name)
                if not mime_type:
                    mime_type = "application/octet-stream"

                file_data_list.append(
                    {
                        "filename": path.name,
                        "content_base64": content_b64,
                        "media_type": mime_type,
                    }
                )
                logger.info(f"[file_data] Prepared file: {path.name} ({len(content)} bytes, {mime_type})")

            except Exception as e:
                logger.error(f"[file_data] Failed to read {path}: {e}")

        return file_data_list

    async def _store_messages_db(
        self,
        request: MessageRequest,
        response: str,
        context: dict[str, Any],
    ) -> None:
        """Store user and assistant messages in the database.

        This is fast and must complete before ResponseEnd so conversation
        history is persisted even if the process crashes.
        """
        if not response:
            return

        db_session_id = context.get("db_session_id")
        if not db_session_id:
            return

        loop = asyncio.get_event_loop()
        user_content = context.get("user_content", request.content)

        await loop.run_in_executor(
            BLOCKING_EXECUTOR,
            lambda: self._store_message(
                db_session_id,
                context["user_id"],
                "user",
                user_content,
            ),
        )
        await loop.run_in_executor(
            BLOCKING_EXECUTOR,
            lambda: self._store_message(
                db_session_id,
                context["user_id"],
                "assistant",
                response,
            ),
        )

    async def _background_memory_ops(
        self,
        request: MessageRequest,
        response: str,
        context: dict[str, Any],
        response_id: str,
    ) -> None:
        """Run memory extraction, vector/graph saves, and FSRS promotion in background.

        These are expensive (5-15s) and don't need to block the user response.
        Errors are logged but don't affect the user experience.
        """
        try:
            # Track sentiment for emotional context
            await self._track_sentiment(request, context)

            # Store in Rook for semantic memory (LLM extraction + vector/graph)
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

            # Maybe evolve personality based on conversation
            await self._maybe_evolve_personality(request, response)

            # Promote memories that were used in this response (FSRS feedback)
            await self._promote_retrieved_memories(context)

            logger.debug(f"Background memory ops completed for {response_id}")
        except Exception as e:
            logger.warning(f"Background memory ops failed for {response_id}: {e}")

        # Notify ORS of user activity (non-blocking, fire-and-forget)
        await self._notify_ors(request, context)

    async def _track_sentiment(
        self,
        request: MessageRequest,
        context: dict[str, Any],
    ) -> None:
        """Track message sentiment for emotional context.

        Args:
            request: The message request
            context: The context dict
        """
        try:
            from clara_core.emotional_context import track_message_sentiment

            track_message_sentiment(
                user_id=context["user_id"],
                channel_id=context["channel_id"],
                message_content=request.content,
            )
        except ImportError:
            pass  # Emotional context module not available
        except Exception as e:
            logger.debug(f"Failed to track sentiment: {e}")

    async def _maybe_evolve_personality(
        self,
        request: MessageRequest,
        response: str,
    ) -> None:
        """Probabilistically evolve personality based on conversation.

        Runs after memory extraction. The probability gate and LLM call
        are handled inside the personality_evolution module.
        """
        try:
            from clara_core.personality_evolution import maybe_evolve_personality

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                BLOCKING_EXECUTOR,
                lambda: maybe_evolve_personality(
                    user_message=request.content,
                    assistant_reply=response,
                ),
            )
        except Exception as e:
            logger.debug(f"Personality evolution check failed: {e}")

    async def _promote_retrieved_memories(self, context: dict[str, Any]) -> None:
        """Promote memories that were retrieved for this response.

        Closes the FSRS feedback loop: memories used in responses
        get stronger (higher retrieval_strength), unused ones naturally
        decay over time.
        """
        user_id = context.get("user_id")
        if not user_id or not self._memory_manager:
            return

        try:
            loop = asyncio.get_event_loop()
            memory_ids = await loop.run_in_executor(
                BLOCKING_EXECUTOR,
                lambda: self._memory_manager.get_last_retrieved_memory_ids(user_id),
            )
            if not memory_ids:
                return

            for memory_id in memory_ids:
                await loop.run_in_executor(
                    BLOCKING_EXECUTOR,
                    lambda mid=memory_id: self._memory_manager.promote_memory(
                        memory_id=mid,
                        user_id=user_id,
                        grade=3,  # Grade.GOOD
                        signal_type="used_in_response",
                    ),
                )

            logger.debug(f"Promoted {len(memory_ids)} memories for user {user_id}")
        except Exception as e:
            logger.warning(f"Failed to promote memories: {e}")

    async def _notify_ors(
        self,
        request: MessageRequest,
        context: dict[str, Any],
    ) -> None:
        """Notify the Organic Response System of user activity.

        Fire-and-forget: failures are logged at debug level and never
        block the user response.
        """
        try:
            from proactive.engine import is_enabled, on_user_message

            if not is_enabled():
                return

            await on_user_message(
                user_id=context["user_id"],
                channel_id=context.get("channel_id", ""),
                message_preview=request.content[:200] if request.content else None,
            )

            # Track proactive responses — if user replies within 1 hour of
            # receiving a proactive message, mark it as responded.
            from proactive.engine import get_proactive_history, on_proactive_response

            history = get_proactive_history(context["user_id"], limit=1)
            if history and not history[0].get("response_received"):
                sent_str = history[0].get("sent_at")
                if sent_str:
                    from datetime import UTC, datetime, timedelta

                    sent_at = datetime.fromisoformat(sent_str)
                    if (datetime.now(UTC).replace(tzinfo=None) - sent_at) < timedelta(hours=1):
                        await on_proactive_response(context["user_id"], context.get("channel_id", ""))
        except Exception as e:
            logger.debug(f"ORS notification failed (non-critical): {e}")

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
            "search_session_history": "🔎",
            "get_session_history": "📜",
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

    async def _classify_tier(self, request: MessageRequest) -> str:
        """Classify message complexity to determine model tier.

        Uses a fast/low-tier model to analyze the message and context
        to determine the appropriate tier.

        Args:
            request: The message request

        Returns:
            Tier string: "high", "mid", or "low"
        """
        loop = asyncio.get_event_loop()

        # Build context from reply chain (last 4 messages)
        context_lines = []
        if request.reply_chain:
            for msg in request.reply_chain[-4:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")[:200]  # Truncate
                context_lines.append(f"[{role}]: {content}")

        context_str = "\n".join(context_lines) if context_lines else "(no prior context)"

        prompt = TIER_CLASSIFICATION_PROMPT.format(
            message=request.content[:500],  # Truncate long messages
            context=context_str,
        )

        try:
            from clara_core import ModelTier, make_llm

            def classify():
                # Use low-tier model for classification
                llm = make_llm(tier=ModelTier.LOW)
                response = llm([{"role": "user", "content": prompt}])
                return response.strip().upper()

            result = await loop.run_in_executor(BLOCKING_EXECUTOR, classify)

            # Parse result
            if "HIGH" in result:
                return "high"
            elif "LOW" in result:
                return "low"
            else:
                return "mid"  # Default to mid

        except Exception as e:
            logger.warning(f"Tier classification failed: {e}, defaulting to mid")
            return "mid"
