"""Sandbox execution environments for Clara.

Provides sandboxed code execution via Docker or E2B.
"""

from sandbox.docker import DockerSandboxManager, DOCKER_TOOLS, DOCKER_AVAILABLE

__all__ = ["DockerSandboxManager", "DOCKER_TOOLS", "DOCKER_AVAILABLE"]
