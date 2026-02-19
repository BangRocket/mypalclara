# Architecture

MyPalClara uses a modular architecture with a central gateway for message processing.

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Gateway Server                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Router    │  │  Processor  │  │    LLM Orchestrator     │  │
│  │  (queuing)  │──│  (context)  │──│  (streaming, tools)     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│         │                                        │               │
│         ▼                                        ▼               │
│  ┌─────────────┐                        ┌─────────────────────┐  │
│  │   Session   │                        │   Tool Executor     │  │
│  │   Manager   │                        │   (MCP, built-in)   │  │
│  └─────────────┘                        └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
         │                                         │
         │ WebSocket                               │
         ▼                                         ▼
┌─────────────────┐                      ┌─────────────────────┐
│ Discord Adapter │                      │   MCP Servers       │
│  (py-cord)      │                      │  (stdio/HTTP)       │
└─────────────────┘                      └─────────────────────┘
┌─────────────────┐
│  Teams Adapter  │
│  (Bot Framework)│
└─────────────────┘
```

## Core Components

### Gateway Server

The gateway (`gateway/`) is the central hub that:
- Accepts WebSocket connections from platform adapters
- Routes messages through the processing pipeline
- Manages sessions and user context
- Coordinates tool execution

Key files:
- `gateway/server.py` - WebSocket server
- `gateway/router.py` - Message routing and queuing
- `gateway/processor.py` - Context building and memory retrieval
- `gateway/llm_orchestrator.py` - LLM calls with streaming and tool detection

### Platform Adapters

Adapters connect platform-specific APIs to the gateway:

**Discord Adapter** (`adapters/discord/`):
- Uses py-cord for Discord API
- Handles message formatting, splitting, and reactions
- Manages channel modes (active/mention/off)

**Teams Adapter** (`adapters/teams/`):
- Uses Bot Framework SDK
- Adaptive Cards for rich responses
- Azure Bot Service authentication

### Memory System

Clara's memory uses mem0 with multiple layers:
- **Vector Store** - pgvector (production) or Qdrant (development)
- **Graph Store** - FalkorDB for relationship tracking
- **Session Store** - SQLAlchemy with SQLite or PostgreSQL

### Tool System

Tools are registered in a unified registry:
- **Built-in Tools** - File operations, code execution, web search
- **MCP Tools** - External MCP servers (stdio or HTTP transport)
- **Integration Tools** - GitHub, Google Workspace, Azure DevOps

## Data Flow

### Message Processing

1. **Adapter receives message** - Platform-specific parsing
2. **Gateway routes message** - Queuing and session lookup
3. **Processor builds context** - Memory retrieval, channel summary
4. **LLM generates response** - With tool calling loop
5. **Response streams back** - Chunked delivery to adapter
6. **Adapter sends response** - Platform-specific formatting

### Tool Execution

1. **LLM requests tool** - JSON tool call in response
2. **Executor validates** - Check tool exists and arguments
3. **Tool runs** - MCP call, sandbox execution, or API call
4. **Result returns** - Text result back to LLM
5. **LLM continues** - May call more tools or finalize response

## Database Schema

### Core Tables

```
projects
├── id (PK)
├── owner_id
└── name

sessions
├── id (PK)
├── project_id (FK)
├── user_id
├── context_id
├── title
├── archived
├── started_at
├── last_activity_at
└── session_summary

messages
├── id (PK)
├── session_id (FK)
├── user_id
├── role
├── content
└── created_at
```

### MCP Tables

```
mcp_servers
├── id (PK)
├── user_id
├── name
├── server_type
├── enabled
├── status
└── total_tool_calls

mcp_tool_calls
├── id (PK)
├── user_id
├── server_name
├── tool_name
├── started_at
├── duration_ms
└── success

mcp_usage_metrics
├── id (PK)
├── user_id
├── server_name
├── date
├── call_count
└── success_count
```

## Configuration

### Environment Variables

See [[Configuration]] for the complete list of environment variables.

### File-Based Config

- `hooks/hooks.yaml` - Gateway event hooks
- `scheduler.yaml` - Scheduled tasks
- `.mcp_servers/` - MCP server configurations

## Scaling Considerations

### Single Instance
- SQLite database
- Qdrant for vectors
- Local MCP servers

### Production (Multi-Instance)
- PostgreSQL for sessions
- pgvector for memory vectors
- Redis for session sharing (future)
- Load balancer for gateway instances
