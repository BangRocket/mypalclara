"""LLM backend abstraction for Clara.

This module provides backward-compatible exports from clara_core.llm.
New code should import directly from clara_core.

Deprecated:
    Import from clara_core instead:
        from clara_core import make_llm, make_llm_streaming, make_llm_with_tools
"""

from __future__ import annotations

# Re-export everything from clara_core.llm for backward compatibility
from clara_core.llm import (
    make_llm,
    make_llm_streaming,
    make_llm_with_tools,
)

# Also export the legacy globals for any code that accesses them directly
import os

TOOL_MODEL = os.getenv("TOOL_MODEL", "")
TOOL_FORMAT = os.getenv("TOOL_FORMAT", "openai").lower()

__all__ = [
    "make_llm",
    "make_llm_streaming",
    "make_llm_with_tools",
    "TOOL_MODEL",
    "TOOL_FORMAT",
]
