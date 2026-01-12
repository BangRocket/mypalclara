"""
System prompts for Clara.
"""

from mypalclara.prompts.clara import (
    CLARA_SYSTEM_PROMPT,
    build_continuation_prompt,
    build_rumination_prompt,
)

__all__ = [
    "CLARA_SYSTEM_PROMPT",
    "build_rumination_prompt",
    "build_continuation_prompt",
]
