"""
Remote sandbox client for the self-hosted sandbox service.

Provides HTTP client for code execution, shell commands, and file operations.
"""

import base64
import logging
import os
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Configuration
SANDBOX_API_URL = os.getenv("SANDBOX_API_URL", "")
SANDBOX_API_KEY = os.getenv("SANDBOX_API_KEY", "")
SANDBOX_TIMEOUT = int(os.getenv("SANDBOX_TIMEOUT", "60"))


@dataclass
class ExecutionResult:
    """Result from code/command execution."""

    success: bool
    output: str = ""
    error: Optional[str] = None
    exit_code: int = 0
    execution_time: float = 0.0


class RemoteSandboxClient:
    """HTTP client for the remote sandbox service."""

    def __init__(
        self,
        api_url: str = "",
        api_key: str = "",
        timeout: int = 60,
    ):
        self.api_url = (api_url or SANDBOX_API_URL).rstrip("/")
        self.api_key = api_key or SANDBOX_API_KEY
        self.timeout = timeout or SANDBOX_TIMEOUT

        if not self.api_url:
            logger.warning("[sandbox] SANDBOX_API_URL not configured")
        if not self.api_key:
            logger.warning("[sandbox] SANDBOX_API_KEY not configured")

    def is_configured(self) -> bool:
        """Check if the client is properly configured."""
        return bool(self.api_url and self.api_key)

    async def health_check(self) -> dict:
        """Check if the sandbox service is healthy."""
        if not self.api_url:
            return {"status": "unconfigured", "error": "SANDBOX_API_URL not set"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/health",
                    timeout=10.0,
                )
                return response.json()
        except Exception as e:
            logger.exception(f"[sandbox] Health check failed: {e}")
            return {"status": "error", "error": str(e)}

    def _headers(self) -> dict:
        """Get request headers with API key."""
        return {"X-API-Key": self.api_key}

    def _parse_response(self, data: dict) -> ExecutionResult:
        """Parse API response into ExecutionResult."""
        return ExecutionResult(
            success=data.get("success", False),
            output=data.get("output", ""),
            error=data.get("error"),
            exit_code=data.get("exit_code", 0),
            execution_time=data.get("execution_time", 0.0),
        )

    async def create_sandbox(self, user_id: str) -> dict:
        """Create or get a sandbox for the user."""
        if not self.is_configured():
            return {"error": "Sandbox not configured"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/sandbox/{user_id}/create",
                    headers=self._headers(),
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"[sandbox] Create sandbox failed: {e.response.text}")
            return {"error": f"HTTP {e.response.status_code}: {e.response.text}"}
        except Exception as e:
            logger.exception(f"[sandbox] Create sandbox failed: {e}")
            return {"error": str(e)}

    async def get_status(self, user_id: str) -> dict:
        """Get status of a user's sandbox."""
        if not self.is_configured():
            return {"error": "Sandbox not configured"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/sandbox/{user_id}/status",
                    headers=self._headers(),
                    timeout=10.0,
                )
                if response.status_code == 404:
                    return {"status": "not_found"}
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.exception(f"[sandbox] Get status failed: {e}")
            return {"error": str(e)}

    async def stop_sandbox(self, user_id: str) -> bool:
        """Stop a user's sandbox."""
        if not self.is_configured():
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/sandbox/{user_id}/stop",
                    headers=self._headers(),
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception as e:
            logger.exception(f"[sandbox] Stop sandbox failed: {e}")
            return False

    async def execute_code(
        self,
        user_id: str,
        code: str,
        description: str = "",
        timeout: int = 30,
    ) -> ExecutionResult:
        """Execute Python code in the sandbox."""
        if not self.is_configured():
            return ExecutionResult(success=False, error="Sandbox not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/sandbox/{user_id}/execute",
                    headers=self._headers(),
                    json={
                        "code": code,
                        "description": description,
                        "timeout": min(timeout, 300),
                    },
                    timeout=float(self.timeout),
                )
                response.raise_for_status()
                return self._parse_response(response.json())
        except httpx.HTTPStatusError as e:
            logger.error(f"[sandbox] Execute code failed: {e.response.text}")
            return ExecutionResult(
                success=False,
                error=f"HTTP {e.response.status_code}: {e.response.text}",
            )
        except Exception as e:
            logger.exception(f"[sandbox] Execute code failed: {e}")
            return ExecutionResult(success=False, error=str(e))

    async def run_shell(
        self,
        user_id: str,
        command: str,
        timeout: int = 60,
    ) -> ExecutionResult:
        """Run a shell command in the sandbox."""
        if not self.is_configured():
            return ExecutionResult(success=False, error="Sandbox not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/sandbox/{user_id}/shell",
                    headers=self._headers(),
                    json={
                        "command": command,
                        "timeout": min(timeout, 300),
                    },
                    timeout=float(self.timeout),
                )
                response.raise_for_status()
                return self._parse_response(response.json())
        except httpx.HTTPStatusError as e:
            logger.error(f"[sandbox] Shell command failed: {e.response.text}")
            return ExecutionResult(
                success=False,
                error=f"HTTP {e.response.status_code}: {e.response.text}",
            )
        except Exception as e:
            logger.exception(f"[sandbox] Shell command failed: {e}")
            return ExecutionResult(success=False, error=str(e))

    async def install_package(
        self,
        user_id: str,
        package: str,
        timeout: int = 120,
    ) -> ExecutionResult:
        """Install a pip package in the sandbox."""
        if not self.is_configured():
            return ExecutionResult(success=False, error="Sandbox not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/sandbox/{user_id}/pip/install",
                    headers=self._headers(),
                    json={
                        "package": package,
                        "timeout": min(timeout, 300),
                    },
                    timeout=float(self.timeout + 60),  # Extra time for installs
                )
                response.raise_for_status()
                return self._parse_response(response.json())
        except httpx.HTTPStatusError as e:
            logger.error(f"[sandbox] Install package failed: {e.response.text}")
            return ExecutionResult(
                success=False,
                error=f"HTTP {e.response.status_code}: {e.response.text}",
            )
        except Exception as e:
            logger.exception(f"[sandbox] Install package failed: {e}")
            return ExecutionResult(success=False, error=str(e))

    async def list_packages(self, user_id: str) -> ExecutionResult:
        """List installed pip packages."""
        if not self.is_configured():
            return ExecutionResult(success=False, error="Sandbox not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/sandbox/{user_id}/pip/list",
                    headers=self._headers(),
                    timeout=30.0,
                )
                response.raise_for_status()
                return self._parse_response(response.json())
        except Exception as e:
            logger.exception(f"[sandbox] List packages failed: {e}")
            return ExecutionResult(success=False, error=str(e))

    async def list_files(
        self,
        user_id: str,
        path: str = "/workspace",
    ) -> ExecutionResult:
        """List files in a directory."""
        if not self.is_configured():
            return ExecutionResult(success=False, error="Sandbox not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/sandbox/{user_id}/files",
                    headers=self._headers(),
                    params={"path": path},
                    timeout=30.0,
                )
                response.raise_for_status()
                return self._parse_response(response.json())
        except Exception as e:
            logger.exception(f"[sandbox] List files failed: {e}")
            return ExecutionResult(success=False, error=str(e))

    async def read_file(self, user_id: str, path: str) -> ExecutionResult:
        """Read a file from the sandbox."""
        if not self.is_configured():
            return ExecutionResult(success=False, error="Sandbox not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/sandbox/{user_id}/file",
                    headers=self._headers(),
                    params={"path": path},
                    timeout=30.0,
                )

                if response.status_code == 404:
                    return ExecutionResult(success=False, error="File not found")

                response.raise_for_status()
                data = response.json()

                content = data.get("content", "")
                if data.get("encoding") == "base64":
                    content = base64.b64decode(content).decode("utf-8", errors="replace")

                return ExecutionResult(success=True, output=content)
        except Exception as e:
            logger.exception(f"[sandbox] Read file failed: {e}")
            return ExecutionResult(success=False, error=str(e))

    async def write_file(
        self,
        user_id: str,
        path: str,
        content: str | bytes,
    ) -> ExecutionResult:
        """Write a file to the sandbox."""
        if not self.is_configured():
            return ExecutionResult(success=False, error="Sandbox not configured")

        try:
            # Handle bytes content
            if isinstance(content, bytes):
                encoded_content = base64.b64encode(content).decode("ascii")
                encoding = "base64"
            else:
                encoded_content = content
                encoding = "utf-8"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/sandbox/{user_id}/file",
                    headers=self._headers(),
                    json={
                        "path": path,
                        "content": encoded_content,
                        "encoding": encoding,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                return self._parse_response(response.json())
        except Exception as e:
            logger.exception(f"[sandbox] Write file failed: {e}")
            return ExecutionResult(success=False, error=str(e))

    async def delete_file(self, user_id: str, path: str) -> ExecutionResult:
        """Delete a file from the sandbox."""
        if not self.is_configured():
            return ExecutionResult(success=False, error="Sandbox not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.api_url}/sandbox/{user_id}/file",
                    headers=self._headers(),
                    params={"path": path},
                    timeout=10.0,
                )
                response.raise_for_status()
                return self._parse_response(response.json())
        except Exception as e:
            logger.exception(f"[sandbox] Delete file failed: {e}")
            return ExecutionResult(success=False, error=str(e))

    async def unzip_file(
        self,
        user_id: str,
        path: str,
        destination: Optional[str] = None,
    ) -> ExecutionResult:
        """Extract an archive file."""
        if not self.is_configured():
            return ExecutionResult(success=False, error="Sandbox not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/sandbox/{user_id}/unzip",
                    headers=self._headers(),
                    json={
                        "path": path,
                        "destination": destination,
                    },
                    timeout=60.0,
                )
                response.raise_for_status()
                return self._parse_response(response.json())
        except Exception as e:
            logger.exception(f"[sandbox] Unzip file failed: {e}")
            return ExecutionResult(success=False, error=str(e))

    async def restart_sandbox(self, user_id: str) -> dict:
        """Restart a user's sandbox."""
        if not self.is_configured():
            return {"error": "Sandbox not configured"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/sandbox/{user_id}/restart",
                    headers=self._headers(),
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.exception(f"[sandbox] Restart sandbox failed: {e}")
            return {"error": str(e)}
