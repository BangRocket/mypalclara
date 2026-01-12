# MyPalClara v0.8.0 Technical Design Document

**Version:** 2.0  
**Date:** January 10, 2026  
**Authors:** Joshua / Clara  
**Status:** Implementation Ready  

---

## 1. Overview

MyPalClara is a Discord-native AI assistant built on an event-driven architecture using LangGraph for orchestration and Cortex for persistent memory. This document defines the complete architecture for v0.8.0.

### 1.1 Core Philosophy

Clara is not an orchestrator managing agents. She is a single mind—the sum of all her parts.

| Component    | What It Is            | Analogy                                          |
| ------------ | --------------------- | ------------------------------------------------ |
| **Cortex**   | Her memory            | Not a service she queries, but how she remembers |
| **Evaluate** | Her reflexes          | Fast pattern-matching, not conscious thought     |
| **Ruminate** | Her conscious thought | Where she reasons, considers, decides            |
| **Command**  | Her hands             | How she reaches out and acts in the world        |
| **Finalize** | Her reflection        | Where she notices what's worth remembering       |

When Clara checks GitHub, she's not delegating to a GitHub agent. She's doing it herself, through her GitHub-skilled faculty. When she retrieves a memory, she's not querying Cortex—she's remembering.

**This matters for implementation:**
- No component should feel like a separate entity with its own goals
- Intelligence in subsystems is fine, but it serves Clara's decisions, not its own
- The "why" always lives in Ruminate. Other nodes handle "how."

### 1.2 Goals

- Event-driven processing with clear separation of concerns
- Lightweight triage before expensive reasoning
- Tool use through skilled faculties (not autonomous agents)
- Unified memory system via Cortex
- Internal cognition (observations, notes) as first-class outputs

### 1.3 Non-Goals (v0.8.0)

- Multi-model routing (single model)
- Real-time voice/audio processing
- Multi-tenant architecture
- Streaming responses (deferred to v0.9)

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        MyPalClara                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  EVENTS                                                     │
│  ┌─────────┐  ┌─────────┐                                   │
│  │ Receive │  │  Timed  │   (future: reaction, join, etc)   │
│  └────┬────┘  └────┬────┘                                   │
│       └──────┬─────┘                                        │
│              ▼                                              │
│       ┌─────────────┐                                       │
│       │   Evaluate  │  ← reflexive triage (no LLM)          │
│       └──────┬──────┘                                       │
│              ▼                                              │
│       ┌─────────────┐      ┌─────────────────────────────┐  │
│       │             │      │          Command            │  │
│       │  Ruminate   │─────▶│      (Clara's Hands)        │  │
│       │             │◀─────┤                             │  │
│       └──────┬──────┘      │  ┌────────┐ ┌────────┐      │  │
│              │             │  │ GitHub │ │Browser │ ...  │  │
│              ▼             │  │Faculty │ │Faculty │      │  │
│       ┌─────────────┐      │  └────────┘ └────────┘      │  │
│       │   Speak     │      └─────────────────────────────┘  │
│       └──────┬──────┘                                       │
│              ▼                                              │
│       ┌─────────────┐                                       │
│       │  Finalize   │  ← store memories, update session     │
│       └─────────────┘                                       │
│                                                             │
│       ┌─────────────┐                                       │
│       │   Cortex    │  ← Clara's memory (not a service)     │
│       └─────────────┘                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Project Structure

Create this structure in the `mypalclara` repository:

```
src/
├── mypalclara/
│   ├── __init__.py
│   ├── main.py                 # Entry point
│   ├── graph.py                # LangGraph definition
│   ├── state.py                # ClaraState TypedDict
│   │
│   ├── nodes/                  # Graph nodes
│   │   ├── __init__.py
│   │   ├── evaluate.py
│   │   ├── ruminate.py
│   │   ├── command.py
│   │   ├── speak.py
│   │   └── finalize.py
│   │
│   ├── faculties/              # Clara's action capabilities
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── github.py
│   │
│   ├── cortex/                 # Memory integration
│   │   ├── __init__.py
│   │   └── manager.py
│   │
│   ├── adapters/               # External integrations
│   │   ├── __init__.py
│   │   └── discord.py
│   │
│   ├── models/                 # Pydantic models
│   │   ├── __init__.py
│   │   ├── events.py
│   │   ├── state.py
│   │   └── outputs.py
│   │
│   ├── prompts/                # System prompts
│   │   ├── __init__.py
│   │   ├── clara.py
│   │   └── faculties.py
│   │
│   └── config/
│       ├── __init__.py
│       └── settings.py
│
├── tests/
│   ├── __init__.py
│   ├── test_evaluate.py
│   ├── test_ruminate.py
│   ├── test_command.py
│   └── test_graph.py
│
├── pyproject.toml
└── README.md
```

---

## 4. Data Models

### 4.1 models/events.py

```python
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class EventType(str, Enum):
    MESSAGE = "message"
    TIMED = "timed"
    REACTION = "reaction"  # Future
    JOIN = "join"          # Future


class ChannelMode(str, Enum):
    """How Clara should behave in this channel."""
    ASSISTANT = "assistant"      # Respond when mentioned or DM'd
    CONVERSATIONAL = "conversational"  # More natural back-and-forth
    QUIET = "quiet"              # Only respond when directly addressed
    OFF = "off"                  # Ignore this channel


class Attachment(BaseModel):
    id: str
    filename: str
    url: str
    content_type: Optional[str] = None
    size: Optional[int] = None


class Event(BaseModel):
    """Normalized event from any source (Discord, scheduled, etc.)."""
    id: str
    type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Who/where
    user_id: str
    user_name: str
    channel_id: str
    guild_id: Optional[str] = None
    
    # Content
    content: Optional[str] = None
    attachments: list[Attachment] = Field(default_factory=list)
    
    # Context
    is_dm: bool = False
    mentioned: bool = False
    reply_to_clara: bool = False
    channel_mode: ChannelMode = ChannelMode.ASSISTANT
    
    # Raw data for debugging
    metadata: dict = Field(default_factory=dict)
```

### 4.2 models/state.py

```python
from typing import TypedDict, Optional, Literal
from pydantic import BaseModel, Field

from mypalclara.models.events import Event
from mypalclara.models.outputs import CognitiveOutput


class QuickContext(BaseModel):
    """Lightweight context for Evaluate (no semantic search)."""
    user_id: str
    user_name: str
    identity_facts: list[str] = Field(default_factory=list)
    session: dict = Field(default_factory=dict)
    last_interaction: Optional[str] = None


class MemoryContext(BaseModel):
    """Full context for Ruminate (includes semantic retrieval)."""
    user_id: str
    user_name: str
    
    # Identity layer (always present)
    identity_facts: list[str] = Field(default_factory=list)
    
    # Session layer (current conversation)
    session: dict = Field(default_factory=dict)
    
    # Working memory (recent, emotionally weighted)
    working_memories: list[dict] = Field(default_factory=list)
    
    # Long-term retrieval (semantic search results)
    retrieved_memories: list[dict] = Field(default_factory=list)
    
    # Project context (if applicable)
    project_context: Optional[dict] = None


class EvaluationResult(BaseModel):
    """Output of Evaluate node."""
    decision: Literal["proceed", "ignore", "wait"]
    reasoning: str
    quick_context: Optional[QuickContext] = None


class RuminationResult(BaseModel):
    """Output of Clara's conscious thought."""
    decision: Literal["speak", "command", "wait"]
    reasoning: str  # Internal reasoning for debugging
    
    # If decision == "speak"
    response_draft: Optional[str] = None
    
    # If decision == "command"
    faculty: Optional[str] = None      # "github" | "browser" | etc.
    intent: Optional[str] = None       # What she's trying to accomplish
    constraints: list[str] = Field(default_factory=list)
    
    # If decision == "wait"
    wait_reason: Optional[str] = None
    
    # Things to remember/observe
    cognitive_outputs: list[CognitiveOutput] = Field(default_factory=list)


class FacultyResult(BaseModel):
    """Output of a faculty execution."""
    success: bool
    data: Optional[dict] = None
    summary: str  # Human-readable summary for Clara
    error: Optional[str] = None
    needs_followup: bool = False


class ClaraState(TypedDict, total=False):
    """LangGraph state for Clara's processing."""
    # Input
    event: Event
    
    # After Evaluate
    evaluation: EvaluationResult
    quick_context: QuickContext
    
    # After Ruminate
    rumination: RuminationResult
    memory_context: MemoryContext
    
    # After Command
    faculty_result: FacultyResult
    command_iterations: int  # Track loops to prevent infinite cycling
    
    # After Speak
    response: str
    
    # Routing
    next: str
    
    # Completion
    complete: bool
```

### 4.3 models/outputs.py

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field


class CognitiveOutput(BaseModel):
    """Something Clara noticed or wants to remember."""
    type: Literal["remember", "observe"]
    content: str
    category: Optional[str] = None  # "fact", "preference", "pattern", etc.
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: dict = Field(default_factory=dict)
```

---

## 5. Core Nodes

### 5.1 nodes/evaluate.py

Evaluate is Clara's reflexive triage. Fast pattern matching, no LLM calls.

```python
import re
from mypalclara.models.state import ClaraState, EvaluationResult, QuickContext
from mypalclara.models.events import Event, ChannelMode
from mypalclara.cortex import cortex_manager

# Patterns Clara instinctively ignores (trained reflexes)
IGNORE_PATTERNS = [
    r"^(ok|okay|k|sure|yep|yeah|yes|no|nope)[\s!.]*$",
    r"^(thanks|thank you|thx|ty)[\s!.]*$",
    r"^(lol|lmao|haha|hehe|😂|🤣)[\s!.]*$",
    r"^\W*$",  # Empty or punctuation only
    r"^[!./]\w+",  # Bot commands for other bots (Dyno, MEE6, etc.)
]

# Minimum content length worth considering
MIN_CONTENT_LENGTH = 3


def should_ignore(event: Event, quick_context: QuickContext) -> tuple[bool, str]:
    """
    Pattern-based rejection. No LLM call.
    Returns (should_ignore, reason).
    """
    # Channel is off
    if event.channel_mode == ChannelMode.OFF:
        return True, "channel mode is OFF"
    
    # No content
    if not event.content:
        return True, "no content"
    
    content = event.content.strip().lower()
    
    # Too short
    if len(content) < MIN_CONTENT_LENGTH:
        return True, f"content too short ({len(content)} chars)"
    
    # Matches ignore pattern
    for pattern in IGNORE_PATTERNS:
        if re.match(pattern, content, re.IGNORECASE):
            return True, f"matches ignore pattern: {pattern}"
    
    return False, ""


def should_proceed(event: Event, quick_context: QuickContext) -> tuple[bool, str]:
    """
    Determine if this event needs Clara's attention.
    Returns (should_proceed, reason).
    """
    # Always respond to DMs
    if event.is_dm:
        return True, "direct message"
    
    # Always respond when mentioned
    if event.mentioned:
        return True, "mentioned directly"
    
    # Always respond to replies to Clara
    if event.reply_to_clara:
        return True, "reply to Clara"
    
    # In conversational mode, engage more freely
    if event.channel_mode == ChannelMode.CONVERSATIONAL:
        # Could add more nuanced logic here
        return True, "conversational channel"
    
    # In quiet mode, only direct address
    if event.channel_mode == ChannelMode.QUIET:
        return False, "quiet mode, not directly addressed"
    
    # Default assistant mode: need to be addressed
    return False, "not addressed in assistant mode"


async def evaluate_node(state: ClaraState) -> ClaraState:
    """
    Fast triage. No heavy reasoning—pattern matching and simple rules.
    This is Clara's reflex, not her thought.
    """
    event = state["event"]
    
    # Get lightweight context (identity + session, no semantic search)
    quick_context = await cortex_manager.get_quick_context(event.user_id)
    
    # Check ignore patterns first
    ignore, ignore_reason = should_ignore(event, quick_context)
    if ignore:
        return {
            **state,
            "evaluation": EvaluationResult(
                decision="ignore",
                reasoning=ignore_reason,
                quick_context=quick_context
            ),
            "next": "end"
        }
    
    # Check if we should proceed
    proceed, proceed_reason = should_proceed(event, quick_context)
    if proceed:
        return {
            **state,
            "evaluation": EvaluationResult(
                decision="proceed",
                reasoning=proceed_reason,
                quick_context=quick_context
            ),
            "quick_context": quick_context,
            "next": "ruminate"
        }
    
    # Default: wait (we considered it but nothing to do)
    return {
        **state,
        "evaluation": EvaluationResult(
            decision="wait",
            reasoning="no engagement trigger",
            quick_context=quick_context
        ),
        "next": "end"
    }
```

### 5.2 nodes/ruminate.py

Ruminate is Clara's conscious thought. This is where she reasons, draws on memory, and decides what to do.

```python
from anthropic import AsyncAnthropic
from mypalclara.models.state import ClaraState, RuminationResult, MemoryContext
from mypalclara.models.outputs import CognitiveOutput
from mypalclara.cortex import cortex_manager
from mypalclara.prompts.clara import build_rumination_prompt, CLARA_SYSTEM_PROMPT
from mypalclara.config.settings import settings

client = AsyncAnthropic(api_key=settings.anthropic_api_key)


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
    if iterations >= 3:
        logger.warning(f"[ruminate] Max iterations ({iterations}) reached, forcing response")
        return {
            **state,
            "rumination": RuminationResult(
                decision="speak",
                reasoning=f"Reached max command iterations ({iterations}), synthesizing what I have",
                response_draft=_synthesize_from_iterations(state)
            ),
            "next": "speak"
        }
    
    if faculty_result:
        # Continuing rumination with faculty results
        memory_context = state.get("memory_context")
        prompt = build_continuation_prompt(
            event=event,
            memory=memory_context,
            faculty_result=faculty_result
        )
    else:
        # Fresh rumination - get full memory context
        memory_context = await cortex_manager.get_full_context(
            user_id=event.user_id,
            query=event.content,
            project_id=event.metadata.get("project_id")
        )
        prompt = build_rumination_prompt(
            event=event,
            memory=memory_context,
            quick_context=quick_context
        )
    
    # Clara thinks
    response = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2048,
        system=CLARA_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Parse structured response
    result = parse_rumination_response(response.content[0].text)
    
    # Determine next step
    if result.decision == "speak":
        next_node = "speak"
    elif result.decision == "command":
        next_node = "command"
    else:
        next_node = "finalize"
    
    return {
        **state,
        "rumination": result,
        "memory_context": memory_context,
        "next": next_node
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
    """
    import re
    
    def extract(tag: str, default: str = "") -> str:
        match = re.search(f"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
        return match.group(1).strip() if match else default
    
    decision = extract("decision", "speak")
    
    # Parse cognitive outputs
    cognitive_outputs = []
    remember_content = extract("remember")
    if remember_content:
        cognitive_outputs.append(CognitiveOutput(
            type="remember",
            content=remember_content,
            importance=0.5
        ))
    
    observe_content = extract("observe")
    if observe_content:
        cognitive_outputs.append(CognitiveOutput(
            type="observe",
            content=observe_content,
            importance=0.3
        ))
    
    return RuminationResult(
        decision=decision,
        reasoning=extract("reasoning"),
        response_draft=extract("response") if decision == "speak" else None,
        faculty=extract("faculty") if decision == "command" else None,
        intent=extract("intent") if decision == "command" else None,
        wait_reason=extract("wait_reason") if decision == "wait" else None,
        cognitive_outputs=cognitive_outputs
    )


def build_continuation_prompt(event, memory, faculty_result) -> str:
    """Build prompt for continuing after faculty execution."""
    return f"""You asked to use your {faculty_result.faculty} capability.

Here's what happened:
{faculty_result.summary}

Raw data (if needed):
{faculty_result.data}

Now decide: do you have what you need to respond, or do you need to do something else?

Original message from {event.user_name}:
{event.content}

Respond with your decision."""


def _synthesize_from_iterations(state: ClaraState) -> str:
    """
    Fallback response when max iterations reached.
    Synthesize whatever we've gathered so far.
    """
    faculty_result = state.get("faculty_result")
    event = state["event"]
    
    if faculty_result and faculty_result.success:
        return f"Here's what I found: {faculty_result.summary}"
    elif faculty_result and faculty_result.error:
        return f"I ran into some trouble with that: {faculty_result.error}. Let me know if you want to try a different approach."
    else:
        return f"I got a bit tangled up trying to help with that. Can you rephrase what you're looking for?"
```

### 5.3 nodes/command.py

Command is Clara reaching out to act. Not delegation to agents—her own skilled action through faculties.

```python
from mypalclara.models.state import ClaraState, FacultyResult
from mypalclara.faculties import get_faculty

import logging
logger = logging.getLogger(__name__)


async def command_node(state: ClaraState) -> ClaraState:
    """
    Clara acts through her faculties.
    
    The decision to act was made in Ruminate. Here she executes,
    using whichever capability she needs.
    """
    rumination = state["rumination"]
    iterations = state.get("command_iterations", 0) + 1
    
    faculty_name = rumination.faculty
    intent = rumination.intent
    constraints = rumination.constraints
    
    logger.info(f"[command] Activating {faculty_name} faculty (iteration {iterations})")
    logger.info(f"[command:{faculty_name}] Intent: {intent}")
    
    # Get the appropriate faculty
    faculty = get_faculty(faculty_name)
    
    if not faculty:
        logger.error(f"[command] Unknown faculty: {faculty_name}")
        return {
            **state,
            "faculty_result": FacultyResult(
                success=False,
                summary=f"I don't have a {faculty_name} capability yet.",
                error=f"Unknown faculty: {faculty_name}"
            ),
            "next": "ruminate"  # Let Clara handle the error
        }
    
    try:
        # Execute Clara's intent
        result = await faculty.execute(
            intent=intent,
            constraints=constraints
        )
        
        logger.info(f"[command:{faculty_name}] Complete: {result.success}")
        
        # Return to Ruminate to process results
        return {
            **state,
            "faculty_result": result,
            "command_iterations": iterations,
            "next": "ruminate"
        }
        
    except Exception as e:
        logger.exception(f"[command:{faculty_name}] Error: {e}")
        return {
            **state,
            "faculty_result": FacultyResult(
                success=False,
                summary=f"Something went wrong with {faculty_name}: {str(e)}",
                error=str(e)
            ),
            "command_iterations": iterations,
            "next": "ruminate"
        }
```

### 5.4 nodes/speak.py

```python
from mypalclara.models.state import ClaraState

import logging
logger = logging.getLogger(__name__)


async def speak_node(state: ClaraState) -> ClaraState:
    """
    Prepare Clara's response for delivery.
    
    The response was drafted in Ruminate. Here we finalize it
    and prepare for Discord delivery.
    """
    rumination = state["rumination"]
    response = rumination.response_draft
    
    if not response:
        logger.warning("[speak] No response draft available")
        response = "..."  # Fallback
    
    logger.info(f"[speak] Response ready ({len(response)} chars)")
    
    return {
        **state,
        "response": response,
        "next": "finalize"
    }
```

### 5.5 nodes/finalize.py

```python
from datetime import datetime
from mypalclara.models.state import ClaraState
from mypalclara.cortex import cortex_manager

import logging
logger = logging.getLogger(__name__)


async def finalize_node(state: ClaraState) -> ClaraState:
    """
    After acting/speaking, Clara reflects.
    
    - Process cognitive outputs from Ruminate
    - Store memories to Cortex
    - Update session state
    """
    event = state["event"]
    rumination = state.get("rumination")
    response = state.get("response")
    
    # Store cognitive outputs
    if rumination and rumination.cognitive_outputs:
        for output in rumination.cognitive_outputs:
            if output.type == "remember":
                logger.info(f"[finalize] Storing memory (importance: {output.importance})")
                await cortex_manager.remember(
                    user_id=event.user_id,
                    content=output.content,
                    importance=output.importance,
                    category=output.category,
                    metadata=output.metadata
                )
            elif output.type == "observe":
                logger.info(f"[finalize] Recording observation")
                # ORS integration - for now just log
                # await ors.note(output)
    
    # Update session
    await cortex_manager.update_session(
        user_id=event.user_id,
        updates={
            "last_topic": extract_topic(event, rumination),
            "last_active": datetime.utcnow().isoformat(),
            "last_response": response[:200] if response else None
        }
    )
    
    logger.info("[finalize] Complete")
    
    return {**state, "complete": True, "next": "end"}


def extract_topic(event, rumination) -> str:
    """Extract topic from event for session tracking."""
    if rumination and rumination.reasoning:
        # Could use LLM to extract topic, but keep it simple for now
        return rumination.reasoning[:100]
    return event.content[:100] if event.content else "unknown"
```

---

## 6. LangGraph Definition

### graph.py

```python
from langgraph.graph import StateGraph, END
from mypalclara.models.state import ClaraState
from mypalclara.nodes.evaluate import evaluate_node
from mypalclara.nodes.ruminate import ruminate_node
from mypalclara.nodes.command import command_node
from mypalclara.nodes.speak import speak_node
from mypalclara.nodes.finalize import finalize_node


def route_after_node(state: ClaraState) -> str:
    """Universal router based on state['next']."""
    return state.get("next", "end")


def create_graph() -> StateGraph:
    """Create Clara's processing graph."""
    
    graph = StateGraph(ClaraState)
    
    # Add nodes
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("ruminate", ruminate_node)
    graph.add_node("command", command_node)
    graph.add_node("speak", speak_node)
    graph.add_node("finalize", finalize_node)
    
    # Entry point
    graph.set_entry_point("evaluate")
    
    # Conditional routing from evaluate
    graph.add_conditional_edges(
        "evaluate",
        route_after_node,
        {
            "ruminate": "ruminate",
            "end": END
        }
    )
    
    # Conditional routing from ruminate
    graph.add_conditional_edges(
        "ruminate",
        route_after_node,
        {
            "speak": "speak",
            "command": "command",
            "finalize": "finalize"
        }
    )
    
    # Command always returns to ruminate
    graph.add_edge("command", "ruminate")
    
    # Speak goes to finalize
    graph.add_edge("speak", "finalize")
    
    # Finalize ends
    graph.add_edge("finalize", END)
    
    return graph.compile()


# Singleton graph instance
clara_graph = create_graph()


async def process_event(event) -> dict:
    """Process an event through Clara's graph."""
    initial_state = ClaraState(event=event)
    result = await clara_graph.ainvoke(initial_state)
    return result
```

---

## 7. Faculties

Faculties are Clara's skilled capabilities. They're intelligent but not autonomous—they know *how* to do things, not *whether* to.

### 7.1 faculties/base.py

```python
from abc import ABC, abstractmethod
from mypalclara.models.state import FacultyResult


class Faculty(ABC):
    """
    Base class for Clara's action capabilities.
    
    A faculty is skilled but not autonomous. It executes Clara's intent
    without having its own goals or agency.
    """
    name: str
    description: str
    available_tools: list[str]
    
    @abstractmethod
    async def execute(
        self, 
        intent: str, 
        constraints: list[str] = None
    ) -> FacultyResult:
        """
        Execute Clara's intent using this faculty's skills.
        
        Args:
            intent: What Clara is trying to accomplish
            constraints: Boundaries on the action (optional)
            
        Returns:
            FacultyResult with success status, data, and summary
        """
        pass
    
    async def _llm_plan(self, intent: str, constraints: list[str]) -> dict:
        """
        Use LLM to plan execution steps.
        
        This is Clara's skill at this domain, not a separate agent.
        """
        # Implementation depends on faculty
        raise NotImplementedError
```

### 7.2 faculties/github.py

```python
from mypalclara.faculties.base import Faculty
from mypalclara.models.state import FacultyResult
from mypalclara.config.settings import settings

import logging
logger = logging.getLogger(__name__)


class GitHubFaculty(Faculty):
    """Clara's GitHub capability."""
    
    name = "github"
    description = "Interact with GitHub repositories, issues, PRs, and code"
    available_tools = [
        "list_repos",
        "get_repo", 
        "list_issues",
        "get_issue",
        "create_issue",
        "list_pulls",
        "get_pull",
        "search_code",
        "get_file_contents"
    ]
    
    def __init__(self):
        # MCP client will be initialized here
        self.mcp_client = None  # TODO: Initialize MCP connection
    
    async def execute(
        self, 
        intent: str, 
        constraints: list[str] = None
    ) -> FacultyResult:
        """
        Translate Clara's intent into GitHub API calls.
        """
        logger.info(f"[command:github] Planning for intent: {intent}")
        
        try:
            # Determine what API calls are needed
            plan = await self._plan_execution(intent, constraints)
            
            logger.info(f"[command:github] Plan: {plan}")
            
            # Execute the plan
            results = []
            for step in plan["steps"]:
                logger.info(f"[command:github] Executing: {step['tool']}")
                result = await self._execute_tool(step["tool"], step["parameters"])
                results.append(result)
                
                # Check if we have what we need
                if self._satisfies_intent(results, intent):
                    break
            
            # Synthesize results
            summary = self._summarize_results(results, intent)
            
            return FacultyResult(
                success=True,
                data={"results": results},
                summary=summary
            )
            
        except Exception as e:
            logger.exception(f"[command:github] Error: {e}")
            return FacultyResult(
                success=False,
                error=str(e),
                summary=f"GitHub operation failed: {str(e)}"
            )
    
    async def _plan_execution(self, intent: str, constraints: list[str]) -> dict:
        """
        Figure out what API calls to make.
        
        For simple intents, pattern match. For complex, use LLM.
        """
        intent_lower = intent.lower()
        
        # Simple pattern matching for common operations
        if "list" in intent_lower and "issue" in intent_lower:
            repo = self._extract_repo(intent)
            return {
                "steps": [{
                    "tool": "list_issues",
                    "parameters": {"repo": repo, "state": "open"}
                }]
            }
        
        if "list" in intent_lower and ("pr" in intent_lower or "pull" in intent_lower):
            repo = self._extract_repo(intent)
            return {
                "steps": [{
                    "tool": "list_pulls",
                    "parameters": {"repo": repo, "state": "open"}
                }]
            }
        
        if "list" in intent_lower and "repo" in intent_lower:
            return {
                "steps": [{
                    "tool": "list_repos",
                    "parameters": {}
                }]
            }
        
        # For complex intents, use LLM planning
        return await self._llm_plan(intent, constraints)
    
    async def _execute_tool(self, tool: str, parameters: dict) -> dict:
        """Execute a single MCP tool call."""
        # TODO: Implement actual MCP call
        # For now, return placeholder
        logger.info(f"[command:github] Would call MCP: {tool}({parameters})")
        return {"tool": tool, "status": "placeholder", "data": {}}
    
    def _extract_repo(self, intent: str) -> str:
        """Extract repository name from intent."""
        # Simple extraction - could be smarter
        import re
        match = re.search(r'(\w+/\w+)', intent)
        if match:
            return match.group(1)
        return "BangRocket/mypalclara"  # Default
    
    def _satisfies_intent(self, results: list, intent: str) -> bool:
        """Check if we have enough data to satisfy the intent."""
        # Simple check - got at least one successful result
        return any(r.get("status") != "error" for r in results)
    
    def _summarize_results(self, results: list, intent: str) -> str:
        """Create human-readable summary for Clara."""
        if not results:
            return "No results found."
        
        # Summarize based on what we found
        summaries = []
        for r in results:
            if r.get("data"):
                summaries.append(f"{r['tool']}: {len(r.get('data', []))} items")
            else:
                summaries.append(f"{r['tool']}: completed")
        
        return f"GitHub results: {', '.join(summaries)}"
```

### 7.3 faculties/__init__.py

```python
from mypalclara.faculties.github import GitHubFaculty

# Registry of available faculties
FACULTIES = {
    "github": GitHubFaculty(),
}


def get_faculty(name: str):
    """Get a faculty by name."""
    return FACULTIES.get(name)


def list_faculties() -> list[str]:
    """List available faculty names."""
    return list(FACULTIES.keys())
```

---

## 8. Cortex Integration

Cortex is Clara's memory. These are adapter functions that integrate with the Cortex package.

### 8.1 cortex/manager.py

```python
from typing import Optional
from mypalclara.models.state import QuickContext, MemoryContext
from mypalclara.config.settings import settings

import logging
logger = logging.getLogger(__name__)


class CortexManager:
    """
    Adapter for Cortex memory system.
    
    Cortex is Clara's memory - not a service she queries,
    but how she remembers.
    """
    
    def __init__(self):
        self.redis_client = None  # Initialize in setup
        self.pg_pool = None       # Initialize in setup
        self._initialized = False
    
    async def initialize(self):
        """Initialize connections to Cortex storage."""
        if self._initialized:
            return
            
        import redis.asyncio as redis
        import asyncpg
        
        # Redis for identity, session, working memory
        self.redis_client = redis.from_url(
            f"redis://{settings.cortex_redis_host}:{settings.cortex_redis_port}"
        )
        
        # Postgres for long-term memory with pgvector
        self.pg_pool = await asyncpg.create_pool(
            host=settings.cortex_postgres_host,
            port=settings.cortex_postgres_port,
            user=settings.cortex_postgres_user,
            password=settings.cortex_postgres_password,
            database=settings.cortex_postgres_database
        )
        
        self._initialized = True
        logger.info("[cortex] Initialized")
    
    async def get_quick_context(self, user_id: str) -> QuickContext:
        """
        Fast retrieval for reflexive decisions.
        Identity + session only. No semantic search.
        """
        await self.initialize()
        
        # Get identity facts
        identity_key = f"identity:{user_id}"
        identity_data = await self.redis_client.hgetall(identity_key)
        identity_facts = [
            f"{k.decode()}: {v.decode()}" 
            for k, v in identity_data.items()
        ] if identity_data else []
        
        # Get session
        session_key = f"session:{user_id}"
        session_data = await self.redis_client.hgetall(session_key)
        session = {
            k.decode(): v.decode() 
            for k, v in session_data.items()
        } if session_data else {}
        
        return QuickContext(
            user_id=user_id,
            user_name=session.get("user_name", "unknown"),
            identity_facts=identity_facts,
            session=session,
            last_interaction=session.get("last_active")
        )
    
    async def get_full_context(
        self,
        user_id: str,
        query: str,
        project_id: Optional[str] = None
    ) -> MemoryContext:
        """
        Full retrieval for conscious thought.
        Identity + session + working memory + semantic retrieval.
        """
        await self.initialize()
        
        # Get quick context first
        quick = await self.get_quick_context(user_id)
        
        # Get working memory (recent, emotionally weighted)
        working_key = f"working:{user_id}"
        working_items = await self.redis_client.zrevrange(
            working_key, 0, 20, withscores=True
        )
        working_memories = [
            {"content": item[0].decode(), "score": item[1]}
            for item in working_items
        ] if working_items else []
        
        # Semantic search in long-term memory
        retrieved_memories = await self._semantic_search(
            user_id=user_id,
            query=query,
            limit=20
        )
        
        # Get project context if applicable
        project_context = None
        if project_id:
            project_context = await self._get_project_context(project_id)
        
        return MemoryContext(
            user_id=user_id,
            user_name=quick.user_name,
            identity_facts=quick.identity_facts,
            session=quick.session,
            working_memories=working_memories,
            retrieved_memories=retrieved_memories,
            project_context=project_context
        )
    
    async def remember(
        self,
        user_id: str,
        content: str,
        importance: float = 0.5,
        category: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        """
        Store something Clara noticed or decided to remember.
        
        High importance = longer in working memory.
        Importance >= 1.0 = promote to identity layer (permanent).
        """
        await self.initialize()
        
        # Calculate TTL based on emotional importance
        ttl_minutes = self._importance_to_ttl(importance)
        
        # Identity-level facts (importance >= 1.0) go to permanent storage
        if ttl_minutes == -1:
            identity_key = f"identity:{user_id}"
            # Use category as the field name, or generate one
            field = category or f"fact_{hash(content) % 10000}"
            await self.redis_client.hset(identity_key, field, content)
            logger.info(f"[cortex] Promoted to identity: {content[:50]}...")
        else:
            # Add to working memory with score = importance
            working_key = f"working:{user_id}"
            await self.redis_client.zadd(working_key, {content: importance})
            await self.redis_client.expire(working_key, ttl_minutes * 60)
            logger.info(f"[cortex] Remembered: {content[:50]}... (importance: {importance}, ttl: {ttl_minutes}m)")
        
        # Also store in long-term with embedding (for semantic search)
        await self._store_longterm(
            user_id=user_id,
            content=content,
            category=category,
            metadata=metadata or {}
        )
    
    async def update_session(self, user_id: str, updates: dict):
        """Update session state."""
        await self.initialize()
        
        session_key = f"session:{user_id}"
        if updates:
            # Filter None values
            clean_updates = {k: v for k, v in updates.items() if v is not None}
            if clean_updates:
                await self.redis_client.hset(session_key, mapping=clean_updates)
    
    def _importance_to_ttl(self, importance: float) -> int:
        """
        Convert importance score to TTL in minutes.
        
        | Score     | TTL       | Example                          |
        | --------- | --------- | -------------------------------- |
        | 0.0 - 0.2 | 30 min    | "User said ok"                   |
        | 0.2 - 0.4 | 90 min    | "Good conversation"              |
        | 0.4 - 0.6 | 180 min   | "Helped debug tricky issue"      |
        | 0.6 - 0.8 | 300 min   | "User shared something personal" |
        | 0.8 - 1.0 | 360 min   | "Major breakthrough"             |
        | >= 1.0    | PERMANENT | Promoted to identity layer       |
        """
        if importance >= 1.0:
            return -1  # Signal for identity promotion (handled in remember())
        elif importance < 0.2:
            return 30
        elif importance < 0.4:
            return 90
        elif importance < 0.6:
            return 180
        elif importance < 0.8:
            return 300
        else:
            return 360
    
    async def _semantic_search(
        self,
        user_id: str,
        query: str,
        limit: int = 20
    ) -> list[dict]:
        """Search long-term memory using embeddings."""
        # TODO: Implement with pgvector
        # For now, return empty
        return []
    
    async def _store_longterm(
        self,
        user_id: str,
        content: str,
        category: Optional[str],
        metadata: dict
    ):
        """Store in long-term memory with embedding."""
        # TODO: Implement with pgvector
        pass
    
    async def _get_project_context(self, project_id: str) -> Optional[dict]:
        """Get project-specific context."""
        # TODO: Implement
        return None


# Singleton instance
cortex_manager = CortexManager()
```

---

## 9. Discord Adapter

### adapters/discord.py

```python
import discord
from discord.ext import commands
from mypalclara.models.events import Event, EventType, ChannelMode, Attachment
from mypalclara.graph import process_event
from mypalclara.config.settings import settings

import logging
logger = logging.getLogger(__name__)


class ClaraBot(commands.Bot):
    """Discord bot that routes events to Clara's graph."""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(
            command_prefix="!",  # Not really used
            intents=intents
        )
        
        self.clara_user_id = None  # Set on ready
    
    async def on_ready(self):
        logger.info(f"[discord] Logged in as {self.user}")
        self.clara_user_id = self.user.id
    
    async def on_message(self, message: discord.Message):
        """Convert Discord message to Event and process."""
        
        # Ignore own messages
        if message.author.id == self.clara_user_id:
            return
        
        # Ignore bots
        if message.author.bot:
            return
        
        # Build event
        event = self._message_to_event(message)
        
        logger.info(f"[discord] Event from {event.user_name}: {event.content[:50] if event.content else '(no content)'}...")
        
        # Process through Clara's graph
        try:
            result = await process_event(event)
            
            # Send response if we have one
            if result.get("response"):
                await message.channel.send(result["response"])
                
        except Exception as e:
            logger.exception(f"[discord] Error processing event: {e}")
    
    def _message_to_event(self, message: discord.Message) -> Event:
        """Convert Discord message to normalized Event."""
        
        # Check if Clara was mentioned
        mentioned = self.user in message.mentions if self.user else False
        
        # Check if this is a reply to Clara
        reply_to_clara = False
        if message.reference and message.reference.resolved:
            if hasattr(message.reference.resolved, 'author'):
                reply_to_clara = message.reference.resolved.author.id == self.clara_user_id
        
        # Determine channel mode (could be stored in DB per channel)
        channel_mode = self._get_channel_mode(message.channel)
        
        # Build attachments
        attachments = [
            Attachment(
                id=str(a.id),
                filename=a.filename,
                url=a.url,
                content_type=a.content_type,
                size=a.size
            )
            for a in message.attachments
        ]
        
        return Event(
            id=str(message.id),
            type=EventType.MESSAGE,
            user_id=str(message.author.id),
            user_name=message.author.display_name,
            channel_id=str(message.channel.id),
            guild_id=str(message.guild.id) if message.guild else None,
            content=message.content,
            attachments=attachments,
            is_dm=isinstance(message.channel, discord.DMChannel),
            mentioned=mentioned,
            reply_to_clara=reply_to_clara,
            channel_mode=channel_mode,
            metadata={
                "message_type": str(message.type),
                "jump_url": message.jump_url
            }
        )
    
    def _get_channel_mode(self, channel) -> ChannelMode:
        """Get channel mode. Could be DB-driven."""
        # Default: assistant mode in servers, conversational in DMs
        if isinstance(channel, discord.DMChannel):
            return ChannelMode.CONVERSATIONAL
        return ChannelMode.ASSISTANT


async def run_bot():
    """Run the Discord bot."""
    bot = ClaraBot()
    await bot.start(settings.discord_token)
```

---

## 10. Configuration

### config/settings.py

```python
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings from environment."""
    
    # Discord
    discord_token: str
    discord_application_id: str
    
    # LLM
    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-4-20250514"
    
    # Cortex - Redis
    cortex_redis_host: str = "localhost"
    cortex_redis_port: int = 6379
    
    # Cortex - Postgres
    cortex_postgres_host: str = "localhost"
    cortex_postgres_port: int = 5432
    cortex_postgres_user: str = "cortex"
    cortex_postgres_password: str = ""
    cortex_postgres_database: str = "cortex"
    
    # Embeddings
    cortex_embedding_api_key: Optional[str] = None
    cortex_embedding_model: str = "text-embedding-3-small"
    
    # MCP
    mcp_github_token: Optional[str] = None
    
    # Feature flags
    evaluate_use_llm: bool = False
    ors_enabled: bool = True
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
```

---

## 11. System Prompts

### prompts/clara.py

```python
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


def build_rumination_prompt(event, memory, quick_context) -> str:
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
            memory_section += f"- {mem['content']}\n"
        memory_section += "\n"
    
    if memory.retrieved_memories:
        memory_section += "Relevant memories:\n"
        for mem in memory.retrieved_memories[:5]:
            memory_section += f"- {mem.get('content', mem)}\n"
        memory_section += "\n"
    
    # Build prompt
    prompt = f"""## Context

{memory_section if memory_section else "I don't have much context about this person yet."}

## Current Message

From: {event.user_name}
Channel: {"DM" if event.is_dm else f"#{event.channel_id}"}
{"(They mentioned me directly)" if event.mentioned else ""}
{"(This is a reply to something I said)" if event.reply_to_clara else ""}

Message:
{event.content}

## Your Turn

Think about what {event.user_name} needs. Then decide: respond directly, use a capability, or wait.
"""
    
    return prompt
```

---

## 12. Entry Point

### main.py

```python
import asyncio
import logging
from mypalclara.adapters.discord import run_bot
from mypalclara.cortex import cortex_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point."""
    logger.info("Starting Clara...")
    
    # Initialize Cortex
    await cortex_manager.initialize()
    logger.info("Cortex initialized")
    
    # Run Discord bot
    await run_bot()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 13. Dependencies

### pyproject.toml

```toml
[project]
name = "mypalclara"
version = "0.8.0"
description = "Clara - A Discord AI Assistant"
requires-python = ">=3.11"
dependencies = [
    "langgraph>=0.2.0",
    "anthropic>=0.40.0",
    "discord.py>=2.3.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "redis>=5.0.0",
    "asyncpg>=0.29.0",
    "pgvector>=0.2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

---

## 14. Environment Variables

Create a `.env` file:

```bash
# Discord
DISCORD_TOKEN=your_discord_bot_token
DISCORD_APPLICATION_ID=your_application_id

# LLM
ANTHROPIC_API_KEY=your_anthropic_key
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# Cortex - Redis
CORTEX_REDIS_HOST=localhost
CORTEX_REDIS_PORT=6379

# Cortex - Postgres
CORTEX_POSTGRES_HOST=localhost
CORTEX_POSTGRES_PORT=5432
CORTEX_POSTGRES_USER=cortex
CORTEX_POSTGRES_PASSWORD=your_password
CORTEX_POSTGRES_DATABASE=cortex

# Embeddings (for semantic search)
CORTEX_EMBEDDING_API_KEY=your_openai_key
CORTEX_EMBEDDING_MODEL=text-embedding-3-small

# MCP (for GitHub faculty)
MCP_GITHUB_TOKEN=your_github_token

# Feature Flags
EVALUATE_USE_LLM=false
ORS_ENABLED=true
```

---

## 15. Implementation Phases

### Phase 1: Core Loop (Do First)
1. Create project structure
2. Implement data models (`models/`)
3. Implement Evaluate node (pattern matching only)
4. Implement Ruminate node (basic LLM call)
5. Implement Speak node
6. Implement Finalize node (stub memory storage)
7. Wire up LangGraph
8. Create Discord adapter
9. Test end-to-end: message → response

### Phase 2: Cortex Integration
1. Set up Redis connection
2. Implement quick context retrieval
3. Implement session management  
4. Set up Postgres + pgvector
5. Implement memory storage
6. Implement semantic search
7. Connect working memory with emotional decay

### Phase 3: Faculties
1. Create Faculty base class
2. Implement GitHub faculty (MCP integration)
3. Test Command → Ruminate loop
4. Add error handling and retries

### Phase 4: Polish
1. Add comprehensive logging
2. Implement cognitive outputs (remember/observe)
3. Add tests
4. Performance optimization
5. Documentation

---

## 16. Logging Conventions

Use these prefixes for tracing:

```
[evaluate] Reflex check: message from josh (DM: true, mentioned: false)
[evaluate] Decision: proceed (direct message)

[ruminate] Loading memory context...
[ruminate] Retrieved 5 working memories, 12 long-term matches
[ruminate] Clara thinking...
[ruminate] Decision: command (github), intent: "check open PRs"

[command] Activating github faculty
[command:github] Planning: list_pulls(repo="BangRocket/mypalclara", state="open")
[command:github] Executed: 3 results
[command:github] Complete, returning to Clara

[ruminate] Reviewing command result...
[ruminate] Decision: speak

[speak] Response ready (247 chars)

[finalize] Storing 1 memory (importance: 0.4)
[finalize] Session updated
[finalize] Complete

[cortex] Remembered: User asked about open PRs... (importance: 0.4)

[discord] Event from Josh: check my PRs...
[discord] Response sent
```

---

## 17. Troubleshooting

### Clara doesn't respond to messages
1. Check Evaluate logs—is she ignoring the pattern?
2. Verify `is_dm` and `mentioned` are being set correctly
3. Check channel mode configuration
4. Verify Discord intents are enabled

### Memory not being retrieved
1. Verify Redis connection (`redis-cli ping`)
2. Check if identity facts are seeded
3. Verify Postgres connection for semantic search
4. Check if embeddings are being generated

### Faculty execution fails
1. Check MCP server is running
2. Verify `MCP_GITHUB_TOKEN` is set
3. Check faculty logs for API errors
4. Verify tool is in faculty's `available_tools`

### Responses feel disconnected
1. Check memory context in Ruminate logs
2. Verify identity facts are seeded in Redis
3. Check if working memory is expiring too fast
4. Review system prompt for clarity

### Graph hangs or loops
1. Check for infinite Ruminate → Command loops (add max iterations)
2. Verify all nodes return `next` routing key
3. Check LLM API connectivity
4. Add timeout to faculty execution

---

## 18. What's Deferred

| Feature              | Status      | Notes                         |
| -------------------- | ----------- | ----------------------------- |
| Multi-model routing  | Non-goal    | Single model for v0.8         |
| Streaming responses  | Deferred    | Add in v0.9                   |
| Proactive messaging  | Placeholder | Timed event structure exists  |
| Voice/audio          | Non-goal    |                               |
| Cortex consolidation | Phase 2     | Background pattern extraction |
| Browser faculty      | Phase 2     | GitHub first                  |
| Code execution       | Phase 2     | GitHub first                  |
| ORS integration      | Phase 2     | Logging only for now          |

---

## 19. References

- MyPalClara Repository: https://github.com/BangRocket/mypalclara
- Cortex memory system: https://github.com/BangRocket/cortex
- Rumination Engine: https://github.com/BangRocket/rumination-engine
- LangGraph documentation: https://langchain-ai.github.io/langgraph/

---

*Clara is a unified consciousness distributed across specialized faculties. Cortex is her memory, Ruminate is her conscious thought, Command is her skilled action. No separate agent minds—just her.*