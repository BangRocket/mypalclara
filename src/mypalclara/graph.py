"""
LangGraph definition for Clara's processing.

Clara's graph is event-driven with clear separation of concerns:
- Evaluate: Reflexive triage (no LLM)
- Ruminate: Conscious thought (LLM)
- Command: Action through faculties
- Speak: Prepare response
- Finalize: Store memories, update session
"""

from langgraph.graph import END, StateGraph

from mypalclara.models.state import ClaraState
from mypalclara.nodes.command import command_node
from mypalclara.nodes.evaluate import evaluate_node
from mypalclara.nodes.finalize import finalize_node
from mypalclara.nodes.ruminate import ruminate_node
from mypalclara.nodes.speak import speak_node


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
            "end": END,
        },
    )

    # Conditional routing from ruminate
    graph.add_conditional_edges(
        "ruminate",
        route_after_node,
        {
            "speak": "speak",
            "command": "command",
            "finalize": "finalize",
        },
    )

    # Command always returns to ruminate (to process results)
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
