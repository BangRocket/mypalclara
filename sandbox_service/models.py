"""Pydantic models for the sandbox service API.

Defines request and response models for all endpoints.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# ============================================================================
# Request Models
# ============================================================================


class ExecuteCodeRequest(BaseModel):
    """Request to execute Python code."""

    code: str = Field(..., description="Python code to execute")
    description: str = Field("", description="Brief description for logging")
    timeout: int = Field(30, ge=1, le=300, description="Execution timeout in seconds")


class ShellCommandRequest(BaseModel):
    """Request to run a shell command."""

    command: str = Field(..., description="Shell command to execute")
    timeout: int = Field(60, ge=1, le=300, description="Execution timeout in seconds")


class WriteFileRequest(BaseModel):
    """Request to write a file."""

    path: str = Field(
        ..., description="File path in sandbox (e.g., /workspace/script.py)"
    )
    content: str = Field(..., description="File content (text or base64 encoded)")
    encoding: str = Field("utf-8", description="Content encoding: 'utf-8' or 'base64'")


class ReadFileRequest(BaseModel):
    """Request to read a file."""

    path: str = Field(..., description="File path to read")


class ListFilesRequest(BaseModel):
    """Request to list files in a directory."""

    path: str = Field("/workspace", description="Directory path to list")


class InstallPackageRequest(BaseModel):
    """Request to install a pip package."""

    package: str = Field(..., description="Package spec (e.g., 'pandas>=2.0')")
    timeout: int = Field(120, ge=1, le=300, description="Installation timeout")


class UnzipRequest(BaseModel):
    """Request to extract an archive."""

    path: str = Field(..., description="Path to archive file")
    destination: str | None = Field(None, description="Extraction destination")


class CreateSandboxRequest(BaseModel):
    """Request to create a sandbox (optional customization)."""

    image: str | None = Field(None, description="Docker image override")
    memory_limit: str | None = Field(None, description="Memory limit (e.g., '1g')")
    cpu_limit: float | None = Field(None, ge=0.1, le=4.0, description="CPU limit")


# ============================================================================
# Response Models
# ============================================================================


class ExecutionResponse(BaseModel):
    """Response from code/command execution."""

    success: bool = Field(..., description="Whether execution succeeded")
    output: str = Field("", description="stdout from execution")
    error: str | None = Field(None, description="stderr or error message")
    exit_code: int = Field(0, description="Process exit code")
    execution_time: float = Field(0.0, description="Execution time in seconds")


class FileEntry(BaseModel):
    """A file or directory entry."""

    name: str
    type: str  # "file" or "directory"
    size: int = 0
    modified: str = ""


class ListFilesResponse(BaseModel):
    """Response from listing files."""

    path: str
    entries: list[FileEntry]


class ReadFileResponse(BaseModel):
    """Response from reading a file."""

    path: str
    content: str
    encoding: str = "utf-8"
    size: int


class SandboxInfo(BaseModel):
    """Information about a sandbox."""

    user_id: str
    container_id: str
    status: str  # running, stopped, not_found
    created_at: datetime
    last_used: datetime
    execution_count: int
    memory_usage_mb: float = 0
    cpu_percent: float = 0


class ServiceInfo(BaseModel):
    """Information about the service."""

    version: str
    available: bool
    docker_version: str = ""
    active_sandboxes: int
    max_sandboxes: int
    host_info: dict = Field(default_factory=dict)


class HealthResponse(BaseModel):
    """Health check response."""

    status: str  # healthy, unhealthy
    docker: bool
    version: str


class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    detail: str | None = None
