# Architecture

MyPalClara uses a gateway architecture with a central WebSocket server for message processing and thin platform adapters.

## System Overview

```
┌──────────────────────────────────────────────────────────────┐
│                      Clara Gateway                           │
│  ┌──────────┐  ┌───────────┐  ┌───────────────────────────┐ │
│  │  Router   │──│ Processor │──│    LLM Orchestrator       │ │
│  │ (queuing) │  │ (context) │  │ (streaming, tool calling) │ │
│  └──────────┘  └───────────┘  └───────────────────────────┘ │
│       │                                  │                   │
│       ▼                                  ▼                   │
│  ┌──────────┐  ┌──────────┐    ┌─────────────────────────┐  │
│  │ Sessions │  │  Rook    │    │    Tool Executor        │  │
│  │          │  │ (memory) │    │ (MCP + built-in tools)  │  │
│  └──────────┘  └──────────┘    └─────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
        │ WebSocket
        ▼
┌────────────┐  ┌────────────┐  ┌────────────┐
│  Discord   │  │   Teams    │  │    CLI     │
│  Adapter   │  │  Adapter   │  │  Adapter   │
└────────────┘  └────────────┘  └────────────┘
```

## Core Components

### Gateway Server

The gateway (`mypalclara/gateway/`) is the central hub that:
- Accepts WebSocket connections from platform adapters
- Routes messages through the processing pipeline
- Manages sessions and user context
- Coordinates tool execution

Key files:
- `mypalclara/gateway/server.py` - WebSocket server
- `mypalclara/gateway/router.py` - Message routing and queuing
- `mypalclara/gateway/processor.py` - Context building and memory retrieval
- `mypalclara/gateway/llm_orchestrator.py` - LLM calls with streaming and tool detection
- `mypalclara/gateway/tool_executor.py` - Tool invocation
- `mypalclara/gateway/session.py` - Session management

### Platform Adapters

Adapters connect platform-specific APIs to the gateway:

**Discord Adapter** (`adapters/discord/`):
- Uses py-cord for Discord API
- Handles message formatting, splitting, and reactions
- Manages channel modes (active/mention/off)
- Streaming responses via message edits

**Teams Adapter** (`adapters/teams/`):
- Uses Bot Framework SDK
- Adaptive Cards for rich responses
- Azure Bot Service authentication

**CLI Adapter** (`adapters/cli/`):
- Interactive terminal with command history
- Markdown rendering for responses
- Shell command execution with approval flow

### LLM Providers

Unified provider architecture in `clara_core/llm/`:

| Provider | Backend | Notes |
|----------|---------|-------|
| `openrouter` | OpenRouter API | Multi-model proxy (default) |
| `anthropic` | Native Anthropic SDK | Supports proxies like clewdr |
| `nanogpt` | NanoGPT API | Moonshot AI models |
| `openai` | OpenAI-compatible | Any compatible endpoint |
| `bedrock` | Amazon Bedrock | AWS-hosted Claude models |
| `azure` | Azure OpenAI | Azure-hosted models |

Key modules:
- `clara_core/llm/providers/base.py` - Abstract `LLMProvider` interface
- `clara_core/llm/providers/langchain.py` - LangChain, DirectAnthropic, DirectOpenAI providers
- `clara_core/llm/providers/registry.py` - Provider caching and factory
- `clara_core/llm/messages.py` - Typed message dataclasses (SystemMessage, UserMessage, etc.)
- `clara_core/llm/formats.py` - Provider-specific format conversion

### Memory System (Rook)

Clara's memory uses Rook with multiple layers:
- **Vector Store** - pgvector (production) or Qdrant (development) for semantic search
- **Graph Store** - FalkorDB or Kuzu for relationship tracking
- **Session Store** - SQLAlchemy with SQLite or PostgreSQL

Configuration in `config/rook.py` with env vars using `ROOK_*` prefix (fallback: `MEM0_*`).

### Tool System

Tools are loaded via the plugin system:
- **Built-in Tools** (`clara_core/core_tools/`) - File operations, code execution, web search, browser, terminal
- **MCP Tools** (`clara_core/mcp/`) - External MCP servers (stdio or HTTP transport)
- **Integration Tools** - GitHub, Azure DevOps, Google Workspace (via MCP or built-in)

Tool registry in `tools/_registry.py` wraps `clara_core/plugins/` for backwards compatibility.

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

- `hooks/hooks.yaml.example` - Gateway event hooks (copy to `hooks.yaml` to activate)
- `config/scheduler.yaml.example` - Scheduled tasks
- `mypalclara/gateway/adapters.yaml` - Adapter configuration
- `.mcp_servers/` - MCP server configurations

## Scaling Considerations

### Single Instance
- SQLite database
- Qdrant for vectors
- Local MCP servers

### Production (Multi-Instance)
- PostgreSQL for sessions
- pgvector for memory vectors
- FalkorDB for graph memory
- Load balancer for gateway instances
