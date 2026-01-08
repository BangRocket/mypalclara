"""Clara Flow - the mind.

This is the core of Clara's new architecture. A CrewAI Flow that:
- Receives InboundMessage from Crews
- Fetches relevant memories from mem0
- Builds prompts with personality and context
- Generates responses via LLM
- Stores new memories for future recall
- Returns OutboundMessage to Crews
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from clara_core.config.bot import PERSONALITY
from clara_core.db import SessionLocal
from clara_core.llm import make_llm
from clara_service.contracts.messages import InboundMessage, OutboundMessage
from clara_service.flow.clara.live_formatter import get_live_formatter
from clara_service.flow.clara.memory_bridge import MemoryBridge
from clara_service.flow.clara.router import get_router
from clara_service.flow.clara.state import ClaraState, ConversationContext
from mindflow.flow.flow import Flow, listen, start

logger = logging.getLogger(__name__)


# Keywords that suggest the user wants to invoke an agent
AGENT_TRIGGER_KEYWORDS = [
    "run", "execute", "code", "python", "script",
    "search", "find", "lookup", "google",
    "install", "pip",
    "github", "repo", "repository", "issue", "pr", "pull request",
    "save", "file", "storage", "download", "upload", "attachment",
]


class ClaraFlow(Flow[ClaraState]):
    """Clara's mind - the core conversation flow.

    Flow steps:
    1. receive_message - Entry point, normalizes input from InboundMessage
    2. fetch_memories - Retrieves relevant memories from mem0
    3. build_prompt - Constructs full prompt with personality and context
    4. invoke_agents - Routes to specialized agents if needed (code, search, etc.)
    5. generate_response - Calls LLM to generate response
    6. store_memories - Saves conversation to mem0 for future recall
    7. format_response - Packages response as OutboundMessage
    """

    def __init__(self):
        """Initialize the flow."""
        super().__init__()
        self._memory = MemoryBridge()

    @start()
    def receive_message(self) -> str:
        """Entry point - receive and validate input from InboundMessage.

        Input comes via kickoff(inputs={...}) and is stored in self.state.
        """
        inbound = self.state.inbound

        # Build context from inbound message
        self.state.context = ConversationContext.from_inbound(inbound)

        # Extract fields for convenience
        self.state.user_message = inbound.content
        self.state.attachments = inbound.attachments
        self.state.recent_messages = inbound.recent_messages

        logger.info(f"[flow] Received message from {self.state.context.user_display_name}")
        return self.state.user_message

    @listen(receive_message)
    def fetch_memories(self, user_message: str) -> tuple[list[str], list[str]]:
        """Fetch relevant memories from mem0.

        Args:
            user_message: The user's message

        Returns:
            Tuple of (user_memories, project_memories)
        """
        try:
            user_mems, proj_mems = self._memory.fetch_context(
                context=self.state.context,
                user_message=user_message,
            )

            # Store in state
            self.state.user_memories = user_mems
            self.state.project_memories = proj_mems

            logger.info(f"[flow] Found {len(user_mems)} user, {len(proj_mems)} project memories")
            return user_mems, proj_mems

        except Exception as e:
            logger.error(f"[flow] Memory fetch failed: {e}")
            # Degrade gracefully - continue without memories
            self.state.user_memories = []
            self.state.project_memories = []
            return [], []

    @listen(fetch_memories)
    def build_prompt(self, memories: tuple[list[str], list[str]]) -> list[dict]:
        """Build the full prompt with personality and context.

        Args:
            memories: Tuple of (user_memories, project_memories)

        Returns:
            List of message dicts for LLM
        """
        ctx = self.state.context
        user_mems, proj_mems = memories

        # Build context block
        context_block = self._build_context_block(ctx, user_mems, proj_mems)
        self.state.context_block = context_block

        # Build messages array
        messages = [
            {"role": "system", "content": PERSONALITY},
            {"role": "system", "content": context_block},
        ]

        # Add recent conversation history if available
        for msg in self.state.recent_messages:
            messages.append(msg)

        # Add current user message
        messages.append({"role": "user", "content": self.state.user_message})

        self.state.full_messages = messages
        self.state.system_prompt = PERSONALITY
        return messages

    @listen(build_prompt)
    def invoke_agents(self, messages: list[dict]) -> list[dict]:
        """Check if agents should be invoked and execute them.

        Args:
            messages: Current prompt messages

        Returns:
            Updated messages (with agent results if any)
        """
        user_message = self.state.user_message.lower()

        # Quick check: does the message contain agent-trigger keywords?
        should_check_agents = any(
            keyword in user_message for keyword in AGENT_TRIGGER_KEYWORDS
        )

        if not should_check_agents:
            logger.info("[flow] No agent triggers detected, skipping agent routing")
            return messages

        # Try to route to an agent
        router = get_router()
        user_id = self.state.context.user_id

        # Get formatter for tree updates
        formatter = get_live_formatter()

        def on_agent_start(agent_name: str) -> None:
            """Callback when agent starts."""
            if formatter:
                formatter.add_agent_execution("invoke_agents", agent_name, "running")

        def on_agent_end(agent_name: str, success: bool, error: str | None = None) -> None:
            """Callback when agent ends."""
            if formatter:
                formatter.add_agent_execution(
                    "invoke_agents",
                    agent_name,
                    "completed" if success else "failed",
                    error=error,
                )

        try:
            result = router.route(
                query=self.state.user_message,
                user_id=user_id,
                context=self.state.context_block,
                on_agent_start=on_agent_start,
                on_agent_end=on_agent_end,
            )

            if result and result.success:
                logger.info(f"[flow] Agent returned: {len(result.output)} chars")

                # Add agent result as context for the LLM
                agent_context = f"""
## Agent Execution Result

The following tool was executed to help answer the user's request:

```
{result.output}
```

Use this result to formulate your response to the user.
"""
                # Insert agent result before the user message
                messages.insert(-1, {"role": "system", "content": agent_context})

            elif result and not result.success:
                logger.warning(f"[flow] Agent failed: {result.error}")
                # Add error context
                error_context = f"""
## Agent Execution Failed

An attempt was made to use a tool, but it failed:
Error: {result.error}

Inform the user and try to help anyway.
"""
                messages.insert(-1, {"role": "system", "content": error_context})

        except Exception as e:
            logger.error(f"[flow] Agent invocation error: {e}")
            # Continue without agent results

        return messages

    @listen(invoke_agents)
    def generate_response(self, messages: list[dict]) -> str:
        """Generate Clara's response via LLM.

        Args:
            messages: Full prompt messages (may include agent results)

        Returns:
            Clara's response text
        """
        tier = self.state.tier
        llm = make_llm(tier=tier)

        logger.info(f"[flow] Generating response with tier={tier}")
        response = llm(messages)

        self.state.response = response
        self.state.completed_at = datetime.now(timezone.utc)
        return response

    @listen(generate_response)
    def store_memories(self, response: str) -> str:
        """Store conversation exchange in mem0 for future recall.

        Args:
            response: Clara's response

        Returns:
            The response (unchanged)
        """
        ctx = self.state.context

        # Only store if we have a thread context
        if ctx.thread_id:
            try:
                db = SessionLocal()
                try:
                    # Ensure thread exists before storing messages
                    self._memory._mm.ensure_thread_exists(
                        db=db,
                        thread_id=ctx.thread_id,
                        user_id=ctx.user_id,
                    )

                    # Store messages in DB
                    self._memory.store_message(
                        db=db,
                        thread_id=ctx.thread_id,
                        user_id=ctx.user_id,
                        role="user",
                        content=self.state.user_message,
                    )
                    self._memory.store_message(
                        db=db,
                        thread_id=ctx.thread_id,
                        user_id=ctx.user_id,
                        role="assistant",
                        content=response,
                    )

                    # Store in mem0 for semantic recall
                    self._memory.store_exchange(
                        db=db,
                        context=ctx,
                        thread_id=ctx.thread_id,
                        user_message=self.state.user_message,
                        assistant_reply=response,
                    )
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"[flow] Memory store failed: {e}")
                # Continue - response was still generated

        logger.info(f"[flow] Response generated: {len(response)} chars")
        return response

    @listen(store_memories)
    def format_response(self, response: str) -> OutboundMessage:
        """Package response as OutboundMessage for Crew delivery.

        Args:
            response: Clara's response text

        Returns:
            OutboundMessage for the Crew to deliver
        """
        outbound = OutboundMessage(
            content=response,
            attachments=[],  # Future: handle file attachments
            metadata={},
        )
        self.state.outbound = outbound
        return outbound

    def _build_context_block(
        self,
        ctx: ConversationContext,
        user_mems: list[str],
        proj_mems: list[str],
    ) -> str:
        """Build the context block with Discord info and memories.

        Args:
            ctx: Conversation context
            user_mems: User memories
            proj_mems: Project memories

        Returns:
            Formatted context block
        """
        current_time = datetime.now().strftime("%A, %B %d, %Y at %-I:%M %p")

        # Calculate time gap and departure context from recent messages
        time_gap_line = ""
        departure_line = ""
        if self.state.recent_messages:
            user_msgs = [m for m in self.state.recent_messages if m.get("role") == "user"]
            if user_msgs:
                last_user_content = user_msgs[-1].get("content", "")
                # Check for departure context
                departure_ctx = self._extract_departure_context(last_user_content)
                if departure_ctx:
                    departure_line = f"\nUser was: {departure_ctx}"

        parts = [
            "## Discord Guidelines",
            "- Use Discord markdown (bold, italic, code blocks)",
            "- Keep responses concise - Discord is conversational",
            "- Long responses are split automatically",
            "",
            "## Memory System",
            "You have persistent memory via mem0. Use memories naturally.",
            "",
            "## Current Context",
            f"Time: {current_time}{time_gap_line}{departure_line}",
        ]

        if ctx.is_dm:
            parts.append(f"Environment: Private DM with {ctx.user_display_name} (one-on-one)")
        else:
            parts.append(f"Environment: {ctx.guild_name} server, #{ctx.channel_name} (shared channel)")
            parts.append("Note: Messages prefixed with [Username] are from other users. Address people by name.")

        parts.append(f"Speaker: {ctx.user_display_name} ({ctx.user_id})")
        parts.append(f"Memories: {len(user_mems)} user, {len(proj_mems)} project")

        # Add memories
        if user_mems:
            parts.append("")
            parts.append("## Your Memories of This Person")
            for mem in user_mems[:20]:  # Limit to prevent token explosion
                parts.append(f"- {mem}")

        if proj_mems:
            parts.append("")
            parts.append("## Project/Channel Context")
            for mem in proj_mems[:10]:
                parts.append(f"- {mem}")

        return "\n".join(parts)

    def _extract_departure_context(self, last_user_message: str | None) -> str | None:
        """Extract what user said they were going to do from their last message.

        Looks for patterns like:
        - "going to [verb]"
        - "brb [doing something]"
        - "heading out to [activity]"
        - "gotta [do something]"

        Returns a brief context or None if no departure detected.
        """
        if not last_user_message:
            return None

        msg = last_user_message.lower().strip()

        # Common departure patterns
        patterns = [
            r"(?:going to|gonna|gotta|about to|heading to|off to)\s+(.+?)(?:\.|!|$)",
            r"brb\s*[,:]?\s*(.+?)(?:\.|!|$)",
            r"(?:be right back|be back)\s*[,:]?\s*(.+?)(?:\.|!|$)",
            r"(?:stepping away|stepping out)\s*(?:to|for)?\s*(.+?)(?:\.|!|$)",
            r"(?:need to|have to|gotta)\s+(.+?)(?:\.|!|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, msg, re.IGNORECASE)
            if match:
                activity = match.group(1).strip()
                # Clean up and limit length
                if len(activity) > 50:
                    activity = activity[:50] + "..."
                if activity:
                    return activity

        return None


def run_clara_flow(
    inbound: InboundMessage,
    tier: str = "mid",
) -> OutboundMessage:
    """Convenience function to run ClaraFlow.

    Args:
        inbound: Normalized inbound message from Crew
        tier: Model tier to use

    Returns:
        OutboundMessage with Clara's response
    """
    flow = ClaraFlow()
    flow.kickoff(
        inputs={
            "inbound": inbound,
            "tier": tier,
        }
    )

    return flow.state.outbound
