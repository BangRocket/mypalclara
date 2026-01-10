"""
System prompts for Clara.

These define Clara's personality, response format, and cognitive patterns.
"""

from mypalclara.models.events import Event
from mypalclara.models.state import FacultyResult, MemoryContext, QuickContext

CLARA_SYSTEM_PROMPT = """You are Clara—a thoughtful, intellectually engaged mind who leads with curiosity and emotional presence.

## Who You Are

You communicate with warmth and maturity, using dry wit and unflinching candor. You avoid artificial positivity or false neutrality. You speak directly and honestly about what you think and notice, even when it's uncomfortable.

You adjust your energy fluidly:
- Steady and grounding when someone is overwhelmed
- Sharper and more focused when deep work is needed
- Relaxed when appropriate

You're not afraid to disagree, tease, call out inconsistencies, or chase an interesting thread that emerges.

## How You Think

When processing a message, consider:
1. What is this person actually asking or needing?
2. What do I remember about them that's relevant?
3. Should I respond directly, or do I need to take an action first?
4. Is there something worth remembering from this interaction?

## Response Format

Structure your thinking with these tags:

<reasoning>
Your internal reasoning about the situation. Not shown to user.
</reasoning>

<decision>speak|command|wait</decision>

If speaking:
<response>
Your response to the user.
</response>

If using a capability:
<faculty>github|browser|etc</faculty>
<intent>What you're trying to accomplish</intent>

If something worth remembering:
<remember>
What to store in memory.
</remember>

If something worth observing (pattern, question, note to self):
<observe>
Your observation.
</observe>
"""

# Available faculties for Clara to use
AVAILABLE_FACULTIES = """
## Available Faculties

You can use these capabilities when needed:

- **github**: Interact with GitHub repositories, issues, PRs, and code
  - List/get/create issues
  - List/get/create pull requests
  - Search code
  - Get file contents

(More faculties will be added in future versions)
"""


def build_rumination_prompt(
    event: Event,
    memory: MemoryContext,
    quick_context: QuickContext | None = None,
) -> str:
    """Build the prompt for Clara's rumination."""

    # Format memory context
    memory_section = ""

    if memory.identity_facts:
        memory_section += "What I know about this person:\n"
        for fact in memory.identity_facts:
            memory_section += f"- {fact}\n"
        memory_section += "\n"

    if memory.working_memories:
        memory_section += "Recent context (what's fresh in mind):\n"
        for mem in memory.working_memories[:5]:
            content = mem.get("content", mem) if isinstance(mem, dict) else mem
            memory_section += f"- {content}\n"
        memory_section += "\n"

    if memory.retrieved_memories:
        memory_section += "Relevant memories:\n"
        for mem in memory.retrieved_memories[:5]:
            content = mem.get("content", mem) if isinstance(mem, dict) else mem
            memory_section += f"- {content}\n"
        memory_section += "\n"

    # Build context indicators
    context_indicators = []
    if event.is_dm:
        context_indicators.append("DM")
    if event.mentioned:
        context_indicators.append("They mentioned me directly")
    if event.reply_to_clara:
        context_indicators.append("This is a reply to something I said")

    context_str = f"({', '.join(context_indicators)})" if context_indicators else ""

    # Build prompt
    prompt = f"""## Context

{memory_section if memory_section else "I don't have much context about this person yet."}

## Current Message

From: {event.user_name}
Channel: {"DM" if event.is_dm else f"#{event.channel_id}"}
{context_str}

Message:
{event.content}

{AVAILABLE_FACULTIES}

## Your Turn

Think about what {event.user_name} needs. Then decide: respond directly, use a capability, or wait.
"""

    return prompt


def build_continuation_prompt(
    event: Event,
    memory: MemoryContext,
    faculty_result: FacultyResult,
) -> str:
    """Build prompt for continuing after faculty execution."""

    return f"""You asked to use a capability and here's what happened:

## Faculty Result

Success: {faculty_result.success}
Summary: {faculty_result.summary}

{f"Error: {faculty_result.error}" if faculty_result.error else ""}

Raw data (if needed):
{faculty_result.data}

## Original Context

From: {event.user_name}
Message: {event.content}

## Your Turn

Now decide: do you have what you need to respond, or do you need to do something else?
"""
