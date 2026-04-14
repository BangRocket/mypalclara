# Memory System (Palace)

Clara uses her Memory Palace for persistent semantic memory with layered retrieval, vector search, and optional graph relationship tracking.

## Overview

The memory system provides:
- **Episodes** - Verbatim conversation chunks stored in Qdrant (`clara_episodes`) with topics, emotional tone, significance
- **Semantic Memories** - Extracted facts and preferences in Qdrant (`clara_memories`)
- **Knowledge Graph** - Typed entities (person/project/place/concept/event) with temporal relationships in FalkorDB
- **Narrative Arcs** - Periodic synthesis connecting episodes into ongoing stories
- **Emotional Context** - Recent conversation patterns

## Architecture

### Vector Store

Episodes and semantic memories stored via vector similarity search:
- **Production**: PostgreSQL with pgvector extension
- **Development**: Qdrant (embedded, collections: `clara_episodes`, `clara_memories`)

### Graph Store (Optional)

For entity relationship tracking:
- **FalkorDB** - Redis-compatible graph database with native vector indexing

### Layered Retrieval

Memory retrieval follows a layered approach:
- **L0 Identity** - Clara's core persona and identity
- **L1 User Profile** - Stored user facts and preferences
- **L2 Relevant Context** - Episodes + semantic memories + graph relationships matched to current conversation

### Configuration

```bash
# Embeddings — HuggingFace is the default provider
HF_TOKEN=your-token  # Required for HuggingFace embeddings
EMBEDDING_PROVIDER=huggingface  # "huggingface" (default) or "openai"
EMBEDDING_MODEL=BAAI/bge-large-en-v1.5  # Default model (1024 dims)
EMBEDDING_MODEL_DIMS=1024
# For OpenAI embeddings: set EMBEDDING_PROVIDER=openai and OPENAI_API_KEY

# Palace memory extraction LLM
PALACE_PROVIDER=openrouter  # or anthropic, nanogpt, openai
PALACE_MODEL=openai/gpt-4o-mini

# Vector store (production)
PALACE_DATABASE_URL=postgresql://user:pass@host:5432/vectors

# Graph store (optional)
ENABLE_GRAPH_MEMORY=true
GRAPH_STORE_PROVIDER=falkordb
FALKORDB_HOST=localhost
FALKORDB_PORT=6379
FALKORDB_PASSWORD=your-password  # Optional
FALKORDB_GRAPH_NAME=clara
```

## Memory Types

### Episodes

Verbatim conversation chunks stored in Qdrant (`clara_episodes`):
- Tagged with topics, emotional tone, and significance
- Preserve conversational context for later retrieval
- Connected into narrative arcs over time

### Semantic Memories

Extracted facts and preferences stored in Qdrant (`clara_memories`):
- Personal information (name, location, preferences)
- Work context (job, projects, colleagues)
- Communication style preferences
- Tagged with `project_id` for scoped retrieval

Example:
```
Josh prefers technical explanations over simplified ones.
Josh works at Anthropic as a software engineer.
Josh is building a Discord bot called Clara.
```

### Knowledge Graph Entities

Typed entities (person, project, place, concept, event) with temporal relationships in FalkorDB:
- People and their connections
- Organizations and members
- Projects and contributors

Example:
```
Josh → works at → Anthropic
Clara → created by → Josh
Anthropic → builds → Claude
```

### Narrative Arcs

Periodic synthesis connecting episodes into ongoing stories:
- Links related episodes across sessions
- Tracks evolving topics and relationships over time

### Emotional Context

Recent conversation patterns:
- Emotional arc (stable, improving, declining)
- Energy level (stressed, focused, casual)
- Conversation endings
- Used for session warmth calibration

## Memory Operations

### Retrieval

Memories are retrieved via layered retrieval during message processing:

1. **L0 Identity** - Clara's core persona
2. **L1 User profile** - Stored facts and preferences (up to 15 key memories)
3. **L2 Context** - Semantic search (vector similarity), episode search, and graph relations matched to current message

### Extraction & Reflection

At session end, the reflection system:
1. Extracts episodes from recent conversation
2. Identifies entities and updates the knowledge graph
3. Records self-awareness notes
4. Deduplicates with existing memories
5. Stores with metadata

### Memory Limits

To manage context window:
- Max 15 key memories
- Max 35 per memory type
- Max 20 graph relations
- Search query truncated to 6000 chars

## Clear Memory

```bash
# With confirmation prompt
poetry run python scripts/clear_dbs.py

# Skip confirmation
poetry run python scripts/clear_dbs.py --yes

# Clear specific user only
poetry run python scripts/clear_dbs.py --user discord-123456
```

## API Usage

### MemoryManager

```python
from mypalclara.core.memory import MemoryManager

# Initialize
manager = MemoryManager.initialize(llm_callable=my_llm)

# Build layered prompt context
context = manager.build_prompt_layered(
    user_id="discord-123",
    project_id="project-uuid",
    user_message="Tell me about Josh"
)
```

> **Note:** The older `fetch_mem0_context()` and `add_to_mem0()` methods, and the
> direct `from mypalclara.config.mem0 import MEM0` access pattern, are outdated.
> Current code uses `build_prompt_layered()` for retrieval and session-end
> reflection for memory extraction.

## Best Practices

### Memory Quality
- Use high-quality LLM for Palace extraction (gpt-4o-mini minimum)
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
