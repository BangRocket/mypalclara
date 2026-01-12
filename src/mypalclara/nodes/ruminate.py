"""
Ruminate Node - Clara's conscious thought.

This is where Clara reasons, draws on memory, and decides what to do.
Single LLM call that considers context and makes a decision.

Decisions:
- speak: Respond directly to the user
- command: Use a faculty (capability) first
- wait: Nothing to do right now
"""

import logging
import re

from anthropic import AsyncAnthropic

from mypalclara.config.settings import settings
from mypalclara import memory
from mypalclara.models.outputs import CognitiveOutput
from mypalclara.models.state import ClaraState, MemoryContext, RuminationResult
from mypalclara.prompts.clara import (
    CLARA_SYSTEM_PROMPT,
    build_continuation_prompt,
    build_rumination_prompt,
)

logger = logging.getLogger(__name__)

# Max command iterations to prevent infinite loops
# Should be high enough for multi-step tasks (get repo, get file, search, etc.)
MAX_COMMAND_ITERATIONS = 8


def _get_client() -> AsyncAnthropic:
    """Get Anthropic client for rumination."""
    return AsyncAnthropic(api_key=settings.anthropic_api_key)


async def ruminate_node(state: ClaraState) -> ClaraState:
    """
    Clara's conscious thought process.

    One LLM call that:
    - Considers the event and context
    - Draws on her memory (Cortex)
    - Decides: speak directly, use a faculty, or wait
    """
    event = state["event"]
    quick_context = state.get("quick_context")

    # Check if we're continuing after a faculty execution
    faculty_result = state.get("faculty_result")
    iterations = state.get("command_iterations", 0)

    # Safety: force resolution if we've looped too many times
    if iterations >= MAX_COMMAND_ITERATIONS:
        logger.warning(f"[ruminate] Max iterations ({iterations}) reached, forcing response")
        return {
            **state,
            "rumination": RuminationResult(
                decision="speak",
                reasoning=f"Reached max command iterations ({iterations}), synthesizing what I have",
                response_draft=_synthesize_from_iterations(state),
            ),
            "next": "speak",
        }

    # Get or build memory context
    if faculty_result:
        # Continuing rumination with faculty results
        memory_context = state.get("memory_context")
        if not memory_context:
            # Fallback if somehow missing
            logger.info("[ruminate] Memory context missing, fetching fresh...")
            memory_context = await memory.get_full_context(
                user_id=event.user_id,
                query=event.content or "",
                project_id=event.metadata.get("project_id"),
            )
        prompt = build_continuation_prompt(
            event=event,
            memory=memory_context,
            faculty_result=faculty_result,
        )
        logger.info(f"[ruminate] Continuing after faculty (iteration {iterations})")
    else:
        # Fresh rumination - get full memory context
        logger.info(f"[ruminate] === STARTING RUMINATION for user={event.user_id} ===")
        logger.info(f"[ruminate] Input: {(event.content or '')[:100]}...")
        memory_context = await memory.get_full_context(
            user_id=event.user_id,
            query=event.content or "",
            project_id=event.metadata.get("project_id"),
        )

        # Log what's being injected into the prompt
        logger.info("[ruminate] Memory context injected into prompt:")
        logger.info(f"[ruminate]   - Identity facts: {len(memory_context.identity_facts)}")
        logger.info(f"[ruminate]   - Working memories: {len(memory_context.working_memories)}")
        logger.info(f"[ruminate]   - Semantic memories: {len(memory_context.retrieved_memories)}")
        logger.info(
            f"[ruminate]   - Session data: {list(memory_context.session.keys()) if memory_context.session else []}"
        )

        if memory_context.identity_facts:
            logger.debug("[ruminate]   Identity facts preview:")
            for fact in memory_context.identity_facts[:3]:
                logger.debug(f"[ruminate]     • {fact[:80]}...")

        if memory_context.retrieved_memories:
            logger.debug("[ruminate]   Top semantic memories:")
            for mem in memory_context.retrieved_memories[:3]:
                sim = mem.get('similarity') or 0
                content = mem.get('content', '')[:60]
                logger.debug(f"[ruminate]     • sim={sim:.3f} | {content}...")

        # Log conversation history
        history_count = len(event.conversation_history) if event.conversation_history else 0
        logger.info(f"[ruminate]   - Conversation history: {history_count} messages")
        if event.conversation_history and history_count > 0:
            logger.debug(f"[ruminate]   First msg: {event.conversation_history[0].author}: {event.conversation_history[0].content[:50]}...")
            logger.debug(f"[ruminate]   Last msg: {event.conversation_history[-1].author}: {event.conversation_history[-1].content[:50]}...")

        prompt = build_rumination_prompt(
            event=event,
            memory=memory_context,
            quick_context=quick_context,
        )
        logger.info("[ruminate] Clara thinking...")

    # Clara thinks
    client = _get_client()
    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2048,
        system=CLARA_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    # Parse structured response
    response_text = response.content[0].text
    result = parse_rumination_response(response_text)

    logger.info(f"[ruminate] Decision: {result.decision}")
    if result.reasoning:
        logger.debug(f"[ruminate] Reasoning: {result.reasoning[:150]}...")

    # Log cognitive outputs (things to remember/observe)
    if result.cognitive_outputs:
        logger.info(f"[ruminate] Cognitive outputs to store: {len(result.cognitive_outputs)}")
        for output in result.cognitive_outputs:
            logger.info(f"[ruminate]   -> {output.type}: {output.content[:80]}... (importance={output.importance})")

    # Determine next step
    if result.decision == "speak":
        next_node = "speak"
        if result.response_draft:
            logger.debug(f"[ruminate] Response preview: {result.response_draft[:100]}...")
    elif result.decision == "command":
        next_node = "command"
        logger.info(f"[ruminate] Faculty: {result.faculty}, Intent: {result.intent}")
    else:
        next_node = "finalize"
        logger.info(f"[ruminate] Wait reason: {result.wait_reason}")

    return {
        **state,
        "rumination": result,
        "memory_context": memory_context,
        "next": next_node,
    }


def parse_rumination_response(text: str) -> RuminationResult:
    """
    Parse Clara's response into structured result.

    Expected format in response:
    <decision>speak|command|wait</decision>
    <reasoning>Internal reasoning</reasoning>
    <response>Response text if speaking</response>
    <faculty>github|browser|etc if commanding</faculty>
    <intent>What to accomplish if commanding</intent>
    <remember>Things to remember</remember>
    <observe>Things to observe</observe>
    """

    def extract(tag: str, default: str = "") -> str:
        match = re.search(f"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
        return match.group(1).strip() if match else default

    decision = extract("decision", "speak")
    if decision not in ("speak", "command", "wait"):
        decision = "speak"

    # Parse cognitive outputs
    cognitive_outputs: list[CognitiveOutput] = []
    remember_content = extract("remember")
    if remember_content:
        cognitive_outputs.append(
            CognitiveOutput(
                type="remember",
                content=remember_content,
                importance=0.5,
            )
        )

    observe_content = extract("observe")
    if observe_content:
        cognitive_outputs.append(
            CognitiveOutput(
                type="observe",
                content=observe_content,
                importance=0.3,
            )
        )

    identity_content = extract("identity")
    if identity_content:
        cognitive_outputs.append(
            CognitiveOutput(
                type="identity",
                content=identity_content,
                importance=0.8,  # Identity facts are high importance
            )
        )

    # Get response - either from tag or fallback to full text
    response_text = extract("response")
    if not response_text and decision == "speak":
        # If no <response> tag, try to use the full text after removing other tags
        # This is a fallback for when the model doesn't follow format exactly
        clean_text = text
        for tag in ["decision", "reasoning", "faculty", "intent", "remember", "observe"]:
            clean_text = re.sub(f"<{tag}>.*?</{tag}>", "", clean_text, flags=re.DOTALL)
        response_text = clean_text.strip()

    return RuminationResult(
        decision=decision,
        reasoning=extract("reasoning"),
        response_draft=response_text if decision == "speak" else None,
        faculty=extract("faculty") if decision == "command" else None,
        intent=extract("intent") if decision == "command" else None,
        wait_reason=extract("wait_reason") if decision == "wait" else None,
        cognitive_outputs=cognitive_outputs,
    )


def _synthesize_from_iterations(state: ClaraState) -> str:
    """
    Fallback response when max iterations reached.
    Synthesize whatever we've gathered so far.
    """
    faculty_result = state.get("faculty_result")

    if faculty_result and faculty_result.success:
        return f"Here's what I found: {faculty_result.summary}"
    elif faculty_result and faculty_result.error:
        return (
            f"I ran into some trouble with that: {faculty_result.error}. "
            "Let me know if you want to try a different approach."
        )
    else:
        return "I got a bit tangled up trying to help with that. Can you rephrase what you're looking for?"
