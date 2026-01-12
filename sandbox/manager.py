"""
Sandbox manager providing unified interface to remote sandbox service.

This module provides a singleton SandboxManager that wraps the RemoteSandboxClient
and provides the interface expected by the code and files faculties.
"""

import logging
from typing import Optional

from sandbox.remote_client import ExecutionResult, RemoteSandboxClient

logger = logging.getLogger(__name__)

# Singleton instance
_manager: Optional["SandboxManager"] = None


def get_sandbox_manager() -> "SandboxManager":
    """Get the singleton sandbox manager instance."""
    global _manager
    if _manager is None:
        _manager = SandboxManager()
    return _manager


class SandboxManager:
    """
    Unified sandbox manager for remote code execution.

    Provides methods for code execution, shell commands, package management,
    and file operations through the remote sandbox service.
    """

    def __init__(self):
        self._client = RemoteSandboxClient()
        logger.info(
            f"[sandbox] Manager initialized (remote: {self._client.api_url or 'not configured'})"
        )

    def is_available(self) -> bool:
        """Check if sandbox is available."""
        return self._client.is_configured()

    async def health_check(self) -> dict:
        """Check sandbox service health."""
        return await self._client.health_check()

    async def get_status(self, user_id: str) -> dict:
        """Get status of a user's sandbox."""
        return await self._client.get_status(user_id)

    async def create_sandbox(self, user_id: str) -> dict:
        """Create or get a sandbox for the user."""
        return await self._client.create_sandbox(user_id)

    async def stop_sandbox(self, user_id: str) -> bool:
        """Stop a user's sandbox."""
        return await self._client.stop_sandbox(user_id)

    async def restart_sandbox(self, user_id: str) -> dict:
        """Restart a user's sandbox."""
        return await self._client.restart_sandbox(user_id)

    # ==========================================================================
    # Code Execution
    # ==========================================================================

    async def execute_code(
        self,
        user_id: str,
        code: str,
        description: str = "",
        timeout: int = 30,
    ) -> ExecutionResult:
        """
        Execute Python code in the sandbox.

        Args:
            user_id: User identifier for sandbox isolation
            code: Python code to execute
            description: Brief description for logging
            timeout: Execution timeout in seconds (max 300)

        Returns:
            ExecutionResult with success, output, error, exit_code, execution_time
        """
        if not self.is_available():
            return ExecutionResult(
                success=False,
                error="Sandbox not configured. Set SANDBOX_API_URL and SANDBOX_API_KEY.",
            )

        return await self._client.execute_code(user_id, code, description, timeout)

    async def run_shell(
        self,
        user_id: str,
        command: str,
        timeout: int = 60,
    ) -> ExecutionResult:
        """
        Run a shell command in the sandbox.

        Args:
            user_id: User identifier for sandbox isolation
            command: Shell command to execute
            timeout: Execution timeout in seconds (max 300)

        Returns:
            ExecutionResult with success, output, error, exit_code, execution_time
        """
        if not self.is_available():
            return ExecutionResult(
                success=False,
                error="Sandbox not configured. Set SANDBOX_API_URL and SANDBOX_API_KEY.",
            )

        return await self._client.run_shell(user_id, command, timeout)

    async def install_package(
        self,
        user_id: str,
        package: str,
        timeout: int = 120,
    ) -> ExecutionResult:
        """
        Install a pip package in the sandbox.

        Args:
            user_id: User identifier for sandbox isolation
            package: Package spec (e.g., 'pandas>=2.0')
            timeout: Installation timeout in seconds (max 300)

        Returns:
            ExecutionResult with success, output, error
        """
        if not self.is_available():
            return ExecutionResult(
                success=False,
                error="Sandbox not configured. Set SANDBOX_API_URL and SANDBOX_API_KEY.",
            )

        return await self._client.install_package(user_id, package, timeout)

    async def list_packages(self, user_id: str) -> ExecutionResult:
        """List installed pip packages in the sandbox."""
        if not self.is_available():
            return ExecutionResult(
                success=False,
                error="Sandbox not configured. Set SANDBOX_API_URL and SANDBOX_API_KEY.",
            )

        return await self._client.list_packages(user_id)

    # ==========================================================================
    # File Operations
    # ==========================================================================

    async def list_files(
        self,
        user_id: str,
        path: str = "/workspace",
    ) -> ExecutionResult:
        """
        List files in a directory.

        Args:
            user_id: User identifier for sandbox isolation
            path: Directory path to list (default: /workspace)

        Returns:
            ExecutionResult with file listing in output
        """
        if not self.is_available():
            return ExecutionResult(
                success=False,
                error="Sandbox not configured. Set SANDBOX_API_URL and SANDBOX_API_KEY.",
            )

        return await self._client.list_files(user_id, path)

    async def read_file(self, user_id: str, path: str) -> ExecutionResult:
        """
        Read a file from the sandbox.

        Args:
            user_id: User identifier for sandbox isolation
            path: File path to read

        Returns:
            ExecutionResult with file content in output
        """
        if not self.is_available():
            return ExecutionResult(
                success=False,
                error="Sandbox not configured. Set SANDBOX_API_URL and SANDBOX_API_KEY.",
            )

        return await self._client.read_file(user_id, path)

    async def write_file(
        self,
        user_id: str,
        path: str,
        content: str | bytes,
    ) -> ExecutionResult:
        """
        Write a file to the sandbox.

        Args:
            user_id: User identifier for sandbox isolation
            path: File path to write
            content: File content (text or bytes)

        Returns:
            ExecutionResult with success status
        """
        if not self.is_available():
            return ExecutionResult(
                success=False,
                error="Sandbox not configured. Set SANDBOX_API_URL and SANDBOX_API_KEY.",
            )

        return await self._client.write_file(user_id, path, content)

    async def delete_file(self, user_id: str, path: str) -> ExecutionResult:
        """
        Delete a file from the sandbox.

        Args:
            user_id: User identifier for sandbox isolation
            path: File path to delete

        Returns:
            ExecutionResult with success status
        """
        if not self.is_available():
            return ExecutionResult(
                success=False,
                error="Sandbox not configured. Set SANDBOX_API_URL and SANDBOX_API_KEY.",
            )

        return await self._client.delete_file(user_id, path)

    async def unzip_file(
        self,
        user_id: str,
        path: str,
        destination: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Extract an archive file in the sandbox.

        Args:
            user_id: User identifier for sandbox isolation
            path: Path to archive file
            destination: Extraction destination (default: same directory)

        Returns:
            ExecutionResult with extraction output
        """
        if not self.is_available():
            return ExecutionResult(
                success=False,
                error="Sandbox not configured. Set SANDBOX_API_URL and SANDBOX_API_KEY.",
            )

        return await self._client.unzip_file(user_id, path, destination)
