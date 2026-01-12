"""
System prompts for the bot.

These define personality, response format, and cognitive patterns.
Personality is loaded from BOT_PERSONALITY_FILE or BOT_PERSONALITY env var.
"""

from mypalclara.config import settings
from mypalclara.models.events import Event
from mypalclara.models.state import FacultyResult, MemoryContext, QuickContext

# Response format instructions appended to the personality
RESPONSE_FORMAT = """
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

If something worth remembering temporarily:
<remember>
What to store in memory.
</remember>

If you learn a core fact about this person (name, job, family, preferences, important dates):
<identity>
The fact in "key: value" format, e.g., "Name: John" or "Works at: Acme Corp"
</identity>

If something worth observing (pattern, question, note to self):
<observe>
Your observation.
</observe>
"""

# Combine personality from config with response format
CLARA_SYSTEM_PROMPT = f"{settings.personality}\n{RESPONSE_FORMAT}"

# Available faculties for Clara to use
AVAILABLE_FACULTIES = """
## Available Faculties

You can use these capabilities when needed:

- **github**: Full GitHub API - repos, issues, PRs, code, releases, workflows
  - List/get/create issues, PRs, releases
  - Read/write files, search code
  - Manage workflows and actions

- **browser**: Web search and browser automation
  - **Web search** via Tavily: search, QnA, context for RAG, extract URLs
  - **Browser automation** via agent-browser with element refs:
    1. `snapshot <url>` - Get interactive elements with refs (@e1, @e2, etc.)
    2. `click @e3` - Click element by ref
    3. `type @e5 "text"` - Type into element by ref
    4. `scroll down/up` - Scroll the page
    5. `screenshot` / `pdf` - Capture page
  - **Workflow**: Always get a `snapshot` first to see available refs, then interact using those refs
  - Refs are deterministic identifiers from the accessibility tree (e.g., @e1 = first interactive element)

- **code**: Code execution and autonomous coding
  - Execute Python in Docker sandbox
  - Run shell commands, manage files
  - Delegate complex tasks to Claude Code
  - **IMPORTANT**: Put actual code/commands in backticks. Examples:
    - Python: "Run Python: `print('hello')`"
    - Shell: "Shell command: `echo hello && ls -la`"
    - Or use code blocks for multi-line code

- **files**: File storage (local or S3/Wasabi cloud)
  - Save, read, list, delete files
  - Persists across sessions
  - Transfer files to/from sandbox

- **google**: Google Workspace integration (official SDK)
  - Sheets: create, read, write, append, manage sheets
  - Drive: list, upload, download, share, move, copy, rename, delete, search
  - Docs: create, read, write, insert text
  - Calendar: list events, create/update/delete events, list calendars, quick add
  - **NOTE**: Calendar is part of google faculty, not a separate "calendar" faculty. Use `<faculty>google</faculty>` for all Google services including calendar.

- **email**: Email monitoring and alerts
  - Connect Gmail or IMAP accounts
  - Configure alert rules and presets
  - Set quiet hours and notifications

- **ado**: Azure DevOps integration
  - Projects, repos, branches, commits
  - Work items, pipelines, builds
  - Wiki, code search, iterations

- **history**: Chat history search
  - Search past messages
  - Get messages from specific users
  - Retrieve older conversations

- **logs**: System logs access
  - Search logs by keyword or level
  - View recent errors and exceptions
  - Debug issues

- **discord**: Cross-channel messaging
  - Send messages to other channels
  - Create rich embeds
  - List available channels
"""


def build_rumination_prompt(
    event: Event,
    memory: MemoryContext,
    quick_context: QuickContext | None = None,
) -> str:
    """Build the prompt for Clara's rumination."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from mypalclara.config.settings import settings

    # Current date/time for temporal context (in configured timezone)
    try:
        tz = ZoneInfo(settings.timezone)
        now = datetime.now(tz)
    except Exception:
        now = datetime.now()
    date_str = now.strftime("%A, %B %d, %Y at %I:%M %p %Z")

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

    # Build conversation history section
    history_section = ""
    if event.conversation_history:
        history_section = "## Recent Conversation\n\n"
        for msg in event.conversation_history[-25:]:  # Last 25 messages
            prefix = "**Clara:**" if msg.is_clara else f"**{msg.author}:**"
            # Truncate long messages
            content = msg.content[:500] + "..." if len(msg.content) > 500 else msg.content
            history_section += f"{prefix} {content}\n\n"

    # Build prompt
    prompt = f"""## Context

**Current time:** {date_str}

{memory_section if memory_section else "I don't have much context about this person yet."}

{history_section}## Current Message

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

    # Format memory context (same as build_rumination_prompt)
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

    return f"""You asked to use a capability and here's what happened:

## Faculty Result

Success: {faculty_result.success}
Summary: {faculty_result.summary}

{f"Error: {faculty_result.error}" if faculty_result.error else ""}

Raw data (if needed):
{faculty_result.data}

## Memory Context

{memory_section if memory_section else "I don't have much context about this person yet."}

## Original Context

From: {event.user_name}
Message: {event.content}

## Your Turn

Now decide: do you have what you need to respond, or do you need to do something else?
"""
