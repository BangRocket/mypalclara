# Clara CrewAI Architecture Spec

## Overview

Rebuild Clara as a CrewAI Flow (the "mind") that only receives input through Crews (specialized worker teams). This is a foundational architecture change—Clara stops being a Discord bot with tools and becomes a persistent mind with crews as her interface to the world.

## Design Philosophy

- **Clara is a Flow** - The mind, decision maker, holds state and memory
- **Crews are interfaces** - How Clara perceives and interacts with the world
- **Reactive only (v1)** - No background processing/rumination yet, purely responds to input
- **Architecture supports expansion** - Adding new crews or rumination later shouldn't require restructuring

## Architecture

```
                    ┌─ Discord Crew (I/O)
                    │
Clara (Flow/Mind) ──┼─ [Future: Email Crew]
                    │
                    └─ [Future: Code Crew, Research Crew, etc.]
```

## v1 Scope

Minimal proof of concept: Discord conversation works through the new architecture.

```
Discord Message → Discord Crew → Clara Flow → Discord Crew → Discord Response
```

### Components to Build

#### 1. Clara Flow (Mind)

The core. A CrewAI Flow that:

- Receives structured input from crews (not raw Discord messages)
- Maintains state (conversation context, current focus)
- Has access to mem0 for long-term memory
- Makes decisions about how to respond
- Delegates responses back through appropriate crews

**Key aspects:**
- System prompt / personality lives here (defines who Clara *is*)
- Memory integration (mem0) - direct Python calls, not through CrewAI
- State management - what is Clara thinking about, what's the context

```python
from crewai.flow.flow import Flow, listen, start

class ClaraFlow(Flow):
    # State: conversation context, memory refs, etc.
    
    @start()
    def receive_input(self):
        # Entry point - receives structured input from a crew
        pass
    
    @listen(receive_input)
    def think(self):
        # Core "thinking" - LLM call with Clara's personality
        # Access mem0 here for relevant memories
        pass
    
    @listen(think)
    def respond(self):
        # Decide how to respond, delegate to appropriate crew
        pass
```

#### 2. Discord Crew

Handles all Discord I/O. This is what the Discord bot actually talks to.

**Responsibilities:**
- Receive raw Discord messages
- Format them into structured input for the Flow (user info, channel context, message content)
- Receive response decisions from the Flow
- Execute Discord responses (send messages, reactions, files, etc.)

**Agents:**
- `MessageProcessor` - Takes raw Discord events, structures them for the mind
- `ResponseExecutor` - Takes Flow decisions, executes them on Discord

**Note:** This crew might be very thin in v1—almost pass-through. That's fine. The structure matters more than complexity right now.

```python
from crewai import Agent, Crew, Task

message_processor = Agent(
    role="Discord Message Processor",
    goal="Convert raw Discord messages into structured input for Clara's mind",
    # ...
)

response_executor = Agent(
    role="Discord Response Executor", 
    goal="Execute Clara's response decisions on Discord",
    # ...
)

discord_crew = Crew(
    agents=[message_processor, response_executor],
    tasks=[...],
    # ...
)
```

#### 3. Discord Bot (Thin Layer)

The actual Discord.py bot becomes a thin shell:

- Listens for Discord events
- Passes them to the Discord Crew
- Receives responses from the Discord Crew
- Sends them to Discord

No logic lives here. It's just the network interface.

```python
@bot.event
async def on_message(message):
    # Package the raw event
    event = {
        "type": "message",
        "content": message.content,
        "author": str(message.author),
        "channel": str(message.channel),
        # ... other context
    }
    
    # Hand to Discord Crew → Flow → Crew → Response
    response = await clara_system.process(event)
    
    # Send response
    if response:
        await message.channel.send(response)
```

## Integration Points

### Memory (mem0)

- Lives in the Flow, not the crews
- Direct Python integration: `from mem0 import Memory`
- Flow queries mem0 when thinking, stores new memories as appropriate
- Crews don't touch memory directly

### Tools

CrewAI has its own tool system. Tools belong to Agents, not the Flow.

For v1, minimal tooling. The Discord Crew might not need tools at all—just formatting and passing data.

Future crews (Code Crew, Research Crew) would have agents with tools:
- Code Crew agents get GitHub tools, file tools
- Research Crew agents get web search, browser tools

### Personality / System Prompt

Clara's personality definition lives in the Flow. This is the "who Clara is" piece:

- Core personality traits
- Communication style  
- Values and approach

This could be a class attribute, a loaded prompt file, or configured at init.

## File Structure (Suggested)

```
clara-crewai/
├── clara/
│   ├── __init__.py
│   ├── flow.py              # ClaraFlow - the mind
│   ├── memory.py            # mem0 integration
│   └── personality.py       # System prompt / personality config
├── crews/
│   ├── __init__.py
│   └── discord/
│       ├── __init__.py
│       ├── crew.py          # Discord Crew definition
│       ├── agents.py        # Message processor, response executor
│       └── tasks.py         # Task definitions
├── interfaces/
│   ├── __init__.py
│   └── discord_bot.py       # Thin Discord.py bot shell
├── config/
│   └── settings.py          # Environment, API keys, etc.
├── main.py                  # Entry point
└── requirements.txt
```

## Open Questions / Decisions for Implementation

1. **Async handling** - Discord.py is async, CrewAI Flows are sync by default. Need to figure out the bridge (probably `asyncio.to_thread` or CrewAI's async support if it exists).

2. **State persistence** - Does Flow state persist across restarts? Or is mem0 the only persistence layer?

3. **Error handling** - If a crew fails, how does the Flow know? How does it recover?

4. **Message batching** - If multiple Discord messages come in fast, does each get its own Flow cycle? Or batch them?

5. **Tool migration** - Current Clara has ~50+ tools. Which ones become Crew tools vs direct Flow capabilities vs deferred to later?

## What to Defer (Not v1)

- Rumination / background processing
- Email Crew
- Code Crew  
- Research Crew
- Browser Crew
- Any crew beyond Discord
- Complex tool migration
- Multi-channel awareness
- Proactive behaviors

## Success Criteria for v1

1. Can send a Discord message to Clara
2. Message flows through Discord Crew → Clara Flow → Discord Crew
3. Clara responds coherently with her personality intact
4. mem0 memories are accessible (Clara remembers things)
5. Architecture is clean enough that adding a new crew is obvious

## Reference Material

- Current Clara codebase (`mypalclara`) - tool implementations, system prompt, memory integration patterns
- CrewAI docs: https://docs.crewai.com/
- CrewAI GitHub: https://github.com/crewAIInc/crewAI

## Notes

This is a rebuild, not a refactor. The current Clara's *behavior* and *personality* should be preserved, but the *architecture* is new. The existing codebase is reference material for what Clara does—the new codebase is how she does it.

The goal is to get the skeleton right. Once Discord Crew → Flow → Discord Crew works, everything else is adding more crews and capabilities. The mind stays stable.
