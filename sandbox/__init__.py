"""
Sandbox client package for remote code execution.

Provides a client for the self-hosted sandbox service.
"""

from sandbox.manager import get_sandbox_manager, SandboxManager
from sandbox.remote_client import RemoteSandboxClient, ExecutionResult

__all__ = [
    "get_sandbox_manager",
    "SandboxManager",
    "RemoteSandboxClient",
    "ExecutionResult",
]
