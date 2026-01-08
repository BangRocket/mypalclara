from mindflow.events.types.agent_events import (
    AgentExecutionCompletedEvent,
    AgentExecutionErrorEvent,
    AgentExecutionStartedEvent,
    LiteAgentExecutionCompletedEvent,
)
from mindflow.events.types.crew_events import (
    CrewKickoffCompletedEvent,
    CrewKickoffFailedEvent,
    CrewKickoffStartedEvent,
    CrewTestCompletedEvent,
    CrewTestFailedEvent,
    CrewTestStartedEvent,
    CrewTrainCompletedEvent,
    CrewTrainFailedEvent,
    CrewTrainStartedEvent,
)
from mindflow.events.types.flow_events import (
    FlowFinishedEvent,
    FlowStartedEvent,
    MethodExecutionFailedEvent,
    MethodExecutionFinishedEvent,
    MethodExecutionStartedEvent,
)
from mindflow.events.types.knowledge_events import (
    KnowledgeQueryCompletedEvent,
    KnowledgeQueryFailedEvent,
    KnowledgeQueryStartedEvent,
    KnowledgeRetrievalCompletedEvent,
    KnowledgeRetrievalStartedEvent,
    KnowledgeSearchQueryFailedEvent,
)
from mindflow.events.types.llm_events import (
    LLMCallCompletedEvent,
    LLMCallFailedEvent,
    LLMCallStartedEvent,
    LLMStreamChunkEvent,
)
from mindflow.events.types.llm_guardrail_events import (
    LLMGuardrailCompletedEvent,
    LLMGuardrailStartedEvent,
)
from mindflow.events.types.mcp_events import (
    MCPConnectionCompletedEvent,
    MCPConnectionFailedEvent,
    MCPConnectionStartedEvent,
    MCPToolExecutionCompletedEvent,
    MCPToolExecutionFailedEvent,
    MCPToolExecutionStartedEvent,
)
from mindflow.events.types.memory_events import (
    MemoryQueryCompletedEvent,
    MemoryQueryFailedEvent,
    MemoryQueryStartedEvent,
    MemoryRetrievalCompletedEvent,
    MemoryRetrievalStartedEvent,
    MemorySaveCompletedEvent,
    MemorySaveFailedEvent,
    MemorySaveStartedEvent,
)
from mindflow.events.types.reasoning_events import (
    AgentReasoningCompletedEvent,
    AgentReasoningFailedEvent,
    AgentReasoningStartedEvent,
)
from mindflow.events.types.task_events import (
    TaskCompletedEvent,
    TaskFailedEvent,
    TaskStartedEvent,
)
from mindflow.events.types.tool_usage_events import (
    ToolUsageErrorEvent,
    ToolUsageFinishedEvent,
    ToolUsageStartedEvent,
)


EventTypes = (
    CrewKickoffStartedEvent
    | CrewKickoffCompletedEvent
    | CrewKickoffFailedEvent
    | CrewTestStartedEvent
    | CrewTestCompletedEvent
    | CrewTestFailedEvent
    | CrewTrainStartedEvent
    | CrewTrainCompletedEvent
    | CrewTrainFailedEvent
    | AgentExecutionStartedEvent
    | AgentExecutionCompletedEvent
    | LiteAgentExecutionCompletedEvent
    | TaskStartedEvent
    | TaskCompletedEvent
    | TaskFailedEvent
    | FlowStartedEvent
    | FlowFinishedEvent
    | MethodExecutionStartedEvent
    | MethodExecutionFinishedEvent
    | MethodExecutionFailedEvent
    | AgentExecutionErrorEvent
    | ToolUsageFinishedEvent
    | ToolUsageErrorEvent
    | ToolUsageStartedEvent
    | LLMCallStartedEvent
    | LLMCallCompletedEvent
    | LLMCallFailedEvent
    | LLMStreamChunkEvent
    | LLMGuardrailStartedEvent
    | LLMGuardrailCompletedEvent
    | AgentReasoningStartedEvent
    | AgentReasoningCompletedEvent
    | AgentReasoningFailedEvent
    | KnowledgeRetrievalStartedEvent
    | KnowledgeRetrievalCompletedEvent
    | KnowledgeQueryStartedEvent
    | KnowledgeQueryCompletedEvent
    | KnowledgeQueryFailedEvent
    | KnowledgeSearchQueryFailedEvent
    | MemorySaveStartedEvent
    | MemorySaveCompletedEvent
    | MemorySaveFailedEvent
    | MemoryQueryStartedEvent
    | MemoryQueryCompletedEvent
    | MemoryQueryFailedEvent
    | MemoryRetrievalStartedEvent
    | MemoryRetrievalCompletedEvent
    | MCPConnectionStartedEvent
    | MCPConnectionCompletedEvent
    | MCPConnectionFailedEvent
    | MCPToolExecutionStartedEvent
    | MCPToolExecutionCompletedEvent
    | MCPToolExecutionFailedEvent
)
