"""Docker-based sandbox manager for the VPS service.

Manages Docker containers for secure code execution with persistent storage.
Adapted from Clara's sandbox/docker.py for the standalone service.
"""

from __future__ import annotations

import asyncio
import io
import os
import tarfile
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import docker
from docker.models.containers import Container

from .config import (
    DATA_DIR,
    DEFAULT_EXECUTION_TIMEOUT,
    DOCKER_CPU,
    DOCKER_IMAGE,
    DOCKER_MEMORY,
    DOCKER_TIMEOUT,
    MAX_CONTAINERS,
    MAX_EXECUTION_TIMEOUT,
)


@dataclass
class ContainerSession:
    """Tracks an active container session."""

    container: Container
    user_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_used: datetime = field(default_factory=lambda: datetime.now(UTC))
    execution_count: int = 0


@dataclass
class ExecutionResult:
    """Result of code execution."""

    success: bool
    output: str
    error: str | None = None
    exit_code: int = 0
    execution_time: float = 0.0


class SandboxManager:
    """Manages Docker containers for sandboxed code execution.

    Features:
    - Per-user persistent containers
    - Persistent storage via host bind mounts
    - Resource limits (memory, CPU)
    - Idle container cleanup
    """

    def __init__(self):
        self._client: docker.DockerClient | None = None
        self._sessions: dict[str, ContainerSession] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None

    @property
    def client(self) -> docker.DockerClient:
        """Get or create Docker client."""
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    @property
    def sessions(self) -> dict[str, ContainerSession]:
        """Get active sessions."""
        return self._sessions

    def is_available(self) -> bool:
        """Check if Docker is available."""
        try:
            self.client.ping()
            return True
        except Exception:
            return False

    def get_docker_version(self) -> str:
        """Get Docker version string."""
        try:
            info = self.client.version()
            return info.get("Version", "unknown")
        except Exception:
            return "unavailable"

    def _container_name(self, user_id: str) -> str:
        """Generate container name for user."""
        safe_id = "".join(c if c.isalnum() else "-" for c in user_id)
        return f"clara-sandbox-{safe_id}"

    def _user_workspace(self, user_id: str) -> str:
        """Get host path for user's persistent workspace."""
        safe_id = "".join(c if c.isalnum() else "-" for c in user_id)
        path = os.path.join(DATA_DIR, safe_id)
        os.makedirs(path, exist_ok=True)
        return path

    async def get_sandbox(self, user_id: str) -> Container | None:
        """Get or create a sandbox container for the user."""
        async with self._lock:
            # Check existing session
            if user_id in self._sessions:
                session = self._sessions[user_id]
                try:
                    session.container.reload()
                    if session.container.status == "running":
                        session.last_used = datetime.now(UTC)
                        return session.container
                except Exception:
                    pass
                # Container not running, remove from sessions
                del self._sessions[user_id]

            # Check container limit
            if len(self._sessions) >= MAX_CONTAINERS:
                return None

            container_name = self._container_name(user_id)

            # Check for existing container
            try:
                container = self.client.containers.get(container_name)
                if container.status != "running":
                    container.start()
                    container.reload()
            except docker.errors.NotFound:
                # Create new container
                workspace = self._user_workspace(user_id)
                container = await self._create_container(container_name, workspace)

            if container:
                self._sessions[user_id] = ContainerSession(
                    container=container,
                    user_id=user_id,
                )

            return container

    async def _create_container(
        self, name: str, workspace_path: str
    ) -> Container | None:
        """Create a new sandbox container."""
        loop = asyncio.get_event_loop()
        try:
            container = await loop.run_in_executor(
                None,
                lambda: self.client.containers.run(
                    DOCKER_IMAGE,
                    name=name,
                    detach=True,
                    stdin_open=True,
                    tty=False,
                    working_dir="/workspace",
                    volumes={
                        workspace_path: {"bind": "/workspace", "mode": "rw"},
                    },
                    mem_limit=DOCKER_MEMORY,
                    cpu_period=100000,
                    cpu_quota=int(DOCKER_CPU * 100000),
                    network_mode="bridge",
                    command=["tail", "-f", "/dev/null"],
                ),
            )
            return container
        except Exception as e:
            print(f"[SandboxManager] Failed to create container: {e}")
            return None

    async def destroy_sandbox(self, user_id: str) -> bool:
        """Destroy a user's sandbox (but preserve workspace files)."""
        async with self._lock:
            if user_id in self._sessions:
                session = self._sessions[user_id]
                try:
                    session.container.stop(timeout=5)
                    session.container.remove(force=True)
                except Exception:
                    pass
                del self._sessions[user_id]
                return True

            # Try to find and remove by name
            try:
                container = self.client.containers.get(self._container_name(user_id))
                container.stop(timeout=5)
                container.remove(force=True)
                return True
            except docker.errors.NotFound:
                pass

        return False

    async def get_sandbox_info(self, user_id: str) -> dict | None:
        """Get information about a user's sandbox."""
        if user_id not in self._sessions:
            return None

        session = self._sessions[user_id]
        try:
            session.container.reload()
            stats = session.container.stats(stream=False)

            # Calculate memory usage
            memory_usage = 0
            if "memory_stats" in stats:
                memory_usage = stats["memory_stats"].get("usage", 0) / (1024 * 1024)

            # Calculate CPU usage
            cpu_percent = 0
            if "cpu_stats" in stats and "precpu_stats" in stats:
                cpu_delta = (
                    stats["cpu_stats"]["cpu_usage"]["total_usage"]
                    - stats["precpu_stats"]["cpu_usage"]["total_usage"]
                )
                system_delta = (
                    stats["cpu_stats"]["system_cpu_usage"]
                    - stats["precpu_stats"]["system_cpu_usage"]
                )
                if system_delta > 0:
                    cpu_percent = (cpu_delta / system_delta) * 100

            return {
                "user_id": user_id,
                "container_id": session.container.short_id,
                "status": session.container.status,
                "created_at": session.created_at,
                "last_used": session.last_used,
                "execution_count": session.execution_count,
                "memory_usage_mb": round(memory_usage, 2),
                "cpu_percent": round(cpu_percent, 2),
            }
        except Exception:
            return None

    async def execute_code(
        self, user_id: str, code: str, timeout: int = DEFAULT_EXECUTION_TIMEOUT
    ) -> ExecutionResult:
        """Execute Python code in the sandbox."""
        container = await self.get_sandbox(user_id)
        if not container:
            return ExecutionResult(
                success=False,
                output="",
                error="Failed to get sandbox container",
            )

        timeout = min(timeout, MAX_EXECUTION_TIMEOUT)
        start_time = time.time()

        try:
            # Write code to temp file
            await self._write_to_container(container, "/tmp/script.py", code)

            # Execute
            loop = asyncio.get_event_loop()
            exit_code, output = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: container.exec_run(
                        ["python", "/tmp/script.py"],
                        workdir="/workspace",
                        demux=True,
                    ),
                ),
                timeout=timeout,
            )

            stdout = output[0].decode("utf-8") if output[0] else ""
            stderr = output[1].decode("utf-8") if output[1] else ""

            # Update session stats
            if user_id in self._sessions:
                self._sessions[user_id].execution_count += 1
                self._sessions[user_id].last_used = datetime.now(UTC)

            return ExecutionResult(
                success=exit_code == 0,
                output=stdout,
                error=stderr if stderr else None,
                exit_code=exit_code,
                execution_time=time.time() - start_time,
            )

        except TimeoutError:
            return ExecutionResult(
                success=False,
                output="",
                error=f"Execution timed out after {timeout} seconds",
                execution_time=timeout,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="",
                error=str(e),
                execution_time=time.time() - start_time,
            )

    async def run_shell(
        self, user_id: str, command: str, timeout: int = 60
    ) -> ExecutionResult:
        """Run a shell command in the sandbox."""
        container = await self.get_sandbox(user_id)
        if not container:
            return ExecutionResult(
                success=False,
                output="",
                error="Failed to get sandbox container",
            )

        timeout = min(timeout, MAX_EXECUTION_TIMEOUT)
        start_time = time.time()

        try:
            loop = asyncio.get_event_loop()
            exit_code, output = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: container.exec_run(
                        ["sh", "-c", command],
                        workdir="/workspace",
                        demux=True,
                    ),
                ),
                timeout=timeout,
            )

            stdout = output[0].decode("utf-8") if output[0] else ""
            stderr = output[1].decode("utf-8") if output[1] else ""

            if user_id in self._sessions:
                self._sessions[user_id].last_used = datetime.now(UTC)

            return ExecutionResult(
                success=exit_code == 0,
                output=stdout,
                error=stderr if stderr else None,
                exit_code=exit_code,
                execution_time=time.time() - start_time,
            )

        except TimeoutError:
            return ExecutionResult(
                success=False,
                output="",
                error=f"Command timed out after {timeout} seconds",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="",
                error=str(e),
            )

    async def install_package(
        self, user_id: str, package: str, timeout: int = 120
    ) -> ExecutionResult:
        """Install a pip package in the sandbox."""
        return await self.run_shell(user_id, f"pip install {package}", timeout=timeout)

    async def read_file(self, user_id: str, path: str) -> ExecutionResult:
        """Read a file from the sandbox."""
        container = await self.get_sandbox(user_id)
        if not container:
            return ExecutionResult(
                success=False,
                output="",
                error="Failed to get sandbox container",
            )

        try:
            loop = asyncio.get_event_loop()
            exit_code, output = await loop.run_in_executor(
                None,
                lambda: container.exec_run(["cat", path], demux=True),
            )

            if exit_code != 0:
                stderr = output[1].decode("utf-8") if output[1] else "File not found"
                return ExecutionResult(
                    success=False,
                    output="",
                    error=stderr,
                    exit_code=exit_code,
                )

            content = output[0].decode("utf-8") if output[0] else ""
            return ExecutionResult(
                success=True,
                output=content,
                exit_code=0,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="",
                error=str(e),
            )

    async def write_file(
        self, user_id: str, path: str, content: str | bytes
    ) -> ExecutionResult:
        """Write a file to the sandbox."""
        container = await self.get_sandbox(user_id)
        if not container:
            return ExecutionResult(
                success=False,
                output="",
                error="Failed to get sandbox container",
            )

        try:
            # Ensure parent directory exists
            dir_path = os.path.dirname(path)
            if dir_path:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: container.exec_run(["mkdir", "-p", dir_path]),
                )

            await self._write_to_container(container, path, content)

            return ExecutionResult(
                success=True,
                output=f"Written {len(content)} bytes to {path}",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="",
                error=str(e),
            )

    async def list_files(
        self, user_id: str, path: str = "/workspace"
    ) -> ExecutionResult:
        """List files in a directory."""
        return await self.run_shell(user_id, f"ls -la '{path}'", timeout=10)

    async def unzip_file(
        self, user_id: str, path: str, destination: str | None = None
    ) -> ExecutionResult:
        """Extract an archive file."""
        dest = destination or os.path.dirname(path) or "/workspace"

        # Detect archive type and build command
        if path.endswith(".zip"):
            cmd = f"unzip -o '{path}' -d '{dest}'"
        elif path.endswith((".tar.gz", ".tgz")):
            cmd = f"tar -xzf '{path}' -C '{dest}'"
        elif path.endswith(".tar.bz2"):
            cmd = f"tar -xjf '{path}' -C '{dest}'"
        elif path.endswith(".tar"):
            cmd = f"tar -xf '{path}' -C '{dest}'"
        else:
            # Try unzip first, then tar
            cmd = f"unzip -o '{path}' -d '{dest}' 2>/dev/null || tar -xf '{path}' -C '{dest}'"

        result = await self.run_shell(user_id, cmd, timeout=60)

        # List extracted files
        if result.success:
            list_result = await self.run_shell(user_id, f"ls -la '{dest}'", timeout=10)
            result.output = f"Extracted to {dest}:\n{list_result.output}"

        return result

    async def _write_to_container(
        self, container: Container, path: str, content: str | bytes
    ) -> None:
        """Write content to a file in the container using tar."""
        if isinstance(content, str):
            content = content.encode("utf-8")

        # Create tar archive in memory
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
            file_info = tarfile.TarInfo(name=os.path.basename(path))
            file_info.size = len(content)
            tar.addfile(file_info, io.BytesIO(content))

        tar_buffer.seek(0)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: container.put_archive(os.path.dirname(path) or "/", tar_buffer),
        )

    async def cleanup_idle_sessions(self) -> int:
        """Clean up containers that have been idle too long."""
        cleaned = 0
        now = datetime.now(UTC)
        idle_threshold = DOCKER_TIMEOUT

        async with self._lock:
            idle_users = [
                user_id
                for user_id, session in self._sessions.items()
                if (now - session.last_used).total_seconds() > idle_threshold
            ]

            for user_id in idle_users:
                session = self._sessions[user_id]
                try:
                    session.container.stop(timeout=5)
                    session.container.remove(force=True)
                except Exception:
                    pass
                del self._sessions[user_id]
                cleaned += 1

        return cleaned

    async def cleanup_all(self) -> None:
        """Clean up all containers (for shutdown)."""
        async with self._lock:
            for session in list(self._sessions.values()):
                try:
                    session.container.stop(timeout=5)
                    session.container.remove(force=True)
                except Exception:
                    pass
            self._sessions.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get service statistics."""
        return {
            "available": self.is_available(),
            "docker_version": self.get_docker_version(),
            "active_sessions": len(self._sessions),
            "max_containers": MAX_CONTAINERS,
            "sessions": {
                user_id: {
                    "container_id": session.container.short_id,
                    "created_at": session.created_at.isoformat(),
                    "last_used": session.last_used.isoformat(),
                    "execution_count": session.execution_count,
                }
                for user_id, session in self._sessions.items()
            },
        }

    async def start_cleanup_loop(self) -> None:
        """Start background cleanup task."""

        async def cleanup_loop():
            while True:
                await asyncio.sleep(60)  # Check every minute
                try:
                    cleaned = await self.cleanup_idle_sessions()
                    if cleaned > 0:
                        print(f"[SandboxManager] Cleaned up {cleaned} idle containers")
                except Exception as e:
                    print(f"[SandboxManager] Cleanup error: {e}")

        self._cleanup_task = asyncio.create_task(cleanup_loop())

    async def stop_cleanup_loop(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass


# Global singleton
_manager: SandboxManager | None = None


def get_manager() -> SandboxManager:
    """Get the global sandbox manager."""
    global _manager
    if _manager is None:
        _manager = SandboxManager()
    return _manager
