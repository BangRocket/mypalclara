# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MindFlow is an agent orchestration framework forked from MindFlow 1.8.0. It enables building multi-agent systems with support for LLM-powered agents, task execution, memory, knowledge management (RAG), and workflow orchestration.

- **Language**: Python 3.10+
- **Build System**: uv (workspace)
- **Cloud Deployment**: MindFlow Cloud (mindflow.jorsh.app)

## Repository Structure

```
mindflow/
├── lib/
│   ├── mindflow/           # Core framework
│   │   ├── src/mindflow/   # Source code
│   │   └── tests/          # Tests
│   ├── mindflow-tools/     # Tool integrations
│   └── devtools/           # Development utilities
├── pyproject.toml          # Workspace configuration
└── conftest.py             # Pytest configuration
```

## Common Commands

```bash
# Install dependencies (using uv)
uv sync

# Run the CLI
uv run mindflow --help

# Create a new crew or flow
uv run mindflow create crew <name>
uv run mindflow create flow <name>

# Run a crew (from within a crew project)
uv run mindflow run

# Kickoff a flow (from within a flow project)
uv run mindflow flow kickoff

# Interactive chat with a crew
uv run mindflow chat

# Train a crew
uv run mindflow train -n <iterations>

# Test/evaluate a crew
uv run mindflow test -n <iterations> -m <model>

# Deploy commands
uv run mindflow deploy create
uv run mindflow deploy push
uv run mindflow deploy status

# Memory management
uv run mindflow reset_memories --all
uv run mindflow log_tasks_outputs

# Trace management
uv run mindflow traces enable
uv run mindflow traces disable
uv run mindflow traces status

# Run tests
uv run pytest lib/mindflow/tests/

# Run linting
uv run ruff check lib/
uv run ruff format lib/
```

## Architecture

### Core Components

**Agent System** (`src/mindflow/agent/`, `src/mindflow/agents/`)
- `Agent` class in `agent/core.py` - autonomous entity with tools, memory, and LLM
- `CrewAgentExecutor` handles tool calling and reasoning loops
- Agent adapters support different agent types

**Crew Orchestration** (`src/mindflow/crew.py`, `src/mindflow/crews/`)
- `Crew` class manages multiple agents and tasks
- Supports sequential and hierarchical process types
- Task delegation and result aggregation

**Flow System** (`src/mindflow/flow/`)
- Event-driven workflow orchestration using decorators: `@start`, `@listen`, `@router`
- State management and persistence
- Human-in-the-loop feedback support

**Task System** (`src/mindflow/task.py`, `src/mindflow/tasks/`)
- Task definition with description, expected output, agent assignment
- Conditional tasks, LLM guardrails, hallucination detection

**LLM Integration** (`src/mindflow/llm.py`, `src/mindflow/llms/`)
- Multi-provider: OpenAI, Anthropic, Azure, Bedrock, Gemini
- LiteLLM wrapper for model abstraction
- Hooks system for pre/post LLM call interceptors
- Extended thinking support (Anthropic)

**Knowledge & RAG** (`src/mindflow/knowledge/`, `src/mindflow/rag/`)
- Vector storage with ChromaDB and Qdrant backends
- Multiple embedding models and source types

**Memory Systems** (`src/mindflow/memory/`)
- Short-term, long-term, entity, and contextual memory
- Multiple storage backends

**Tool System** (`src/mindflow/tools/`)
- `BaseTool` abstraction with structured tool arguments
- MCP (Model Context Protocol) integration for tool discovery

**Event System** (`src/mindflow/events/`)
- Central event bus with pub-sub pattern
- Event types for tasks, LLM calls, tools, flows, memory, knowledge

### Key Patterns

- Pydantic v2 throughout for type safety and validation
- Event-driven architecture with central event bus
- Decorator pattern for flow methods (`@start`, `@listen`, `@router`)
- Strategy pattern for process types (sequential, hierarchical)

### Major Files by Size

- `flow/flow.py` (88KB) - Flow orchestration engine
- `llm.py` (86KB) - LLM wrapper and management
- `crew.py` (71KB) - Crew orchestration
- `task.py` (44KB) - Task definition and execution
- `telemetry/telemetry.py` (38KB) - Telemetry system
- `tools/tool_usage.py` (36KB) - Tool tracking
- `mcp/client.py` (26KB) - MCP client
