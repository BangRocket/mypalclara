"""
Clara's processing nodes.

- Evaluate: Reflexive triage (no LLM)
- Ruminate: Conscious thought (LLM)
- Command: Action through faculties
- Speak: Prepare response
- Finalize: Store memories, update session
"""

from mypalclara.nodes.command import command_node
from mypalclara.nodes.evaluate import evaluate_node
from mypalclara.nodes.finalize import finalize_node
from mypalclara.nodes.ruminate import ruminate_node
from mypalclara.nodes.speak import speak_node

__all__ = [
    "evaluate_node",
    "ruminate_node",
    "command_node",
    "speak_node",
    "finalize_node",
]
