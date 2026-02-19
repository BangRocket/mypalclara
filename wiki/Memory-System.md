# Memory System

Clara uses [mem0](https://github.com/mem0ai/mem0) for persistent semantic memory with vector search and optional graph relationship tracking.

## Overview

The memory system provides:
- **User Memories** - Personal facts, preferences, and context
- **Project Memories** - Topic-specific knowledge
- **Key Memories** - Important facts always included
- **Graph Relations** - Entity relationships (optional)
- **Emotional Context** - Recent conversation patterns

## Architecture

### Vector Store

For semantic similarity search:
- **Production**: PostgreSQL with pgvector extension
- **Development**: Qdrant (embedded)

### Graph Store (Optional)

For entity relationship tracking:
- **FalkorDB** - Redis-compatible graph database with native vector indexing

### Configuration

```bash
# Required for embeddings
OPENAI_API_KEY=your-key

# Memory extraction LLM
MEM0_PROVIDER=openrouter  # or anthropic, nanogpt, openai
MEM0_MODEL=openai/gpt-4o-mini

# Vector store (production)
MEM0_DATABASE_URL=postgresql://user:pass@host:5432/vectors

# Graph store (optional)
ENABLE_GRAPH_MEMORY=true
GRAPH_STORE_PROVIDER=falkordb
FALKORDB_HOST=localhost
FALKORDB_PORT=6379
FALKORDB_PASSWORD=your-password  # Optional
FALKORDB_GRAPH_NAME=clara
```

## Memory Types

### User Memories

Persistent facts about users:
- Personal information (name, location, preferences)
- Work context (job, projects, colleagues)
- Communication style preferences
- Historical interactions

Example:
```
Josh prefers technical explanations over simplified ones.
Josh works at Anthropic as a software engineer.
Josh is building a Discord bot called Clara.
```

### Project Memories

Topic-specific knowledge:
- Design decisions and constraints
- Architecture choices
- Terminology and conventions
- World-building details (for creative projects)

Tagged with `project_id` for scoped retrieval.

### Key Memories

High-priority facts always included in context:
- Marked with `is_key: true` metadata
- Limited to 15 per user
- Examples: name, critical preferences

### Graph Relations

Entity relationships extracted from conversations:
- People and their connections
- Organizations and members
- Projects and contributors

Example:
```
Josh → works at → Anthropic
Clara → created by → Josh
Anthropic → builds → Claude
```

### Emotional Context

Recent conversation patterns stored as memories:
- Emotional arc (stable, improving, declining)
- Energy level (stressed, focused, casual)
- Conversation endings
- Used for session warmth calibration

## Memory Operations

### Retrieval

Memories are retrieved during message processing:

1. **Key memories** - Always fetched (up to 15)
2. **Semantic search** - Vector similarity on user message
3. **Participant search** - Memories about mentioned people
4. **Graph relations** - Related entity connections

### Extraction

After each conversation exchange:
1. Recent messages sent to mem0
2. LLM extracts relevant facts
3. Deduplication with existing memories
4. Storage with metadata

### Memory Limits

To manage context window:
- Max 15 key memories
- Max 35 per memory type
- Max 20 graph relations
- Search query truncated to 6000 chars

## Clear Memory

```bash
# With confirmation prompt
poetry run python clear_dbs.py

# Skip confirmation
poetry run python clear_dbs.py --yes

# Clear specific user only
poetry run python clear_dbs.py --user discord-123456
```

## API Usage

### MemoryManager

```python
from clara_core.memory import MemoryManager

# Initialize
manager = MemoryManager.initialize(llm_callable=my_llm)

# Fetch memories
user_mems, proj_mems, graph_rels = manager.fetch_mem0_context(
    user_id="discord-123",
    project_id="project-uuid",
    user_message="Tell me about Josh"
)

# Add memories from conversation
manager.add_to_mem0(
    user_id="discord-123",
    project_id="project-uuid",
    recent_msgs=messages,
    user_message="I prefer Python over JavaScript",
    assistant_reply="Noted! I'll prioritize Python examples."
)
```

### Direct mem0 Access

```python
from config.mem0 import MEM0

# Search memories
results = MEM0.search(
    "Josh's work",
    user_id="discord-123",
    agent_id="clara"
)

# Add memory
MEM0.add(
    [{"role": "user", "content": "My name is Josh"}],
    user_id="discord-123",
    agent_id="clara"
)

# Get all memories
all_mems = MEM0.get_all(user_id="discord-123")
```

## Best Practices

### Memory Quality
- Use high-quality LLM for extraction (gpt-4o-mini minimum)
- Review bootstrap profile for accuracy
- Periodically audit key memories

### Performance
- Disable graph memory if not needed
- Use pgvector in production for speed
- Limit concurrent memory operations

### Privacy
- User memories are scoped by user_id
- Agent memories use agent_id (e.g., "clara")
- Consider data retention policies
