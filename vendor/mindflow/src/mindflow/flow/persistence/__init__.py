"""
MindFlow Flow Persistence.

This module provides interfaces and implementations for persisting flow states.
"""

from typing import Any, TypeVar

from pydantic import BaseModel

from mindflow.flow.persistence.base import FlowPersistence
from mindflow.flow.persistence.decorators import persist
from mindflow.flow.persistence.sqlite import SQLiteFlowPersistence


__all__ = ["FlowPersistence", "SQLiteFlowPersistence", "persist"]

StateType = TypeVar("StateType", bound=dict[str, Any] | BaseModel)
DictStateType = dict[str, Any]
