"""FastAPI application for the sandbox service.

Provides HTTP API for sandbox lifecycle, code execution, and file operations.
"""

from __future__ import annotations

import base64
import shutil
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from . import __version__
from .config import API_KEY, MAX_CONTAINERS, validate_config
from .models import (
    CreateSandboxRequest,
    ExecuteCodeRequest,
    ExecutionResponse,
    HealthResponse,
    InstallPackageRequest,
    ReadFileResponse,
    SandboxInfo,
    ServiceInfo,
    ShellCommandRequest,
    UnzipRequest,
    WriteFileRequest,
)
from .sandbox_manager import ExecutionResult, get_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Validate configuration
    errors = validate_config()
    if errors:
        print(f"[API] Configuration errors: {errors}")
        # Continue anyway for health checks to work

    # Start cleanup loop
    manager = get_manager()
    await manager.start_cleanup_loop()
    print(f"[API] Sandbox service v{__version__} started")

    yield

    # Cleanup on shutdown
    print("[API] Shutting down...")
    await manager.stop_cleanup_loop()
    await manager.cleanup_all()
    print("[API] Shutdown complete")


app = FastAPI(
    title="Clara Sandbox Service",
    description="Self-hosted sandbox API for secure code execution",
    version=__version__,
    lifespan=lifespan,
)


# ============================================================================
# Authentication
# ============================================================================


async def verify_api_key(x_api_key: Annotated[str, Header()]) -> str:
    """Verify API key from header."""
    if not API_KEY:
        raise HTTPException(
            status_code=500,
            detail="API key not configured on server",
        )
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
        )
    return x_api_key


# ============================================================================
# Health & Info Endpoints (no auth required for health)
# ============================================================================


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Check service health (no authentication required)."""
    manager = get_manager()
    return HealthResponse(
        status="healthy" if manager.is_available() else "unhealthy",
        docker=manager.is_available(),
        version=__version__,
    )


@app.get(
    "/info",
    response_model=ServiceInfo,
    tags=["Health"],
    dependencies=[Depends(verify_api_key)],
)
async def service_info() -> ServiceInfo:
    """Get service information."""
    manager = get_manager()
    stats = manager.get_stats()

    # Get host info
    disk = shutil.disk_usage("/")
    host_info = {
        "disk_free_gb": round(disk.free / (1024**3), 2),
        "disk_total_gb": round(disk.total / (1024**3), 2),
    }

    return ServiceInfo(
        version=__version__,
        available=stats["available"],
        docker_version=stats["docker_version"],
        active_sandboxes=stats["active_sessions"],
        max_sandboxes=MAX_CONTAINERS,
        host_info=host_info,
    )


# ============================================================================
# Sandbox Lifecycle Endpoints
# ============================================================================


@app.post(
    "/sandbox/{user_id}/create",
    response_model=SandboxInfo,
    tags=["Sandbox"],
    dependencies=[Depends(verify_api_key)],
)
async def create_sandbox(
    user_id: str,
    request: CreateSandboxRequest | None = None,
) -> SandboxInfo:
    """Create or get a sandbox for the user."""
    manager = get_manager()

    # Check container limit
    if len(manager.sessions) >= MAX_CONTAINERS:
        raise HTTPException(
            status_code=503,
            detail=f"Maximum containers ({MAX_CONTAINERS}) reached",
        )

    container = await manager.get_sandbox(user_id)
    if not container:
        raise HTTPException(
            status_code=503,
            detail="Failed to create sandbox container",
        )

    session = manager.sessions.get(user_id)
    if not session:
        raise HTTPException(
            status_code=500,
            detail="Session not found after creation",
        )

    return SandboxInfo(
        user_id=user_id,
        container_id=container.short_id,
        status="running",
        created_at=session.created_at,
        last_used=session.last_used,
        execution_count=session.execution_count,
    )


@app.get(
    "/sandbox/{user_id}/status",
    response_model=SandboxInfo,
    tags=["Sandbox"],
    dependencies=[Depends(verify_api_key)],
)
async def sandbox_status(user_id: str) -> SandboxInfo:
    """Get status of a user's sandbox."""
    manager = get_manager()
    info = await manager.get_sandbox_info(user_id)

    if not info:
        raise HTTPException(
            status_code=404,
            detail="Sandbox not found",
        )

    return SandboxInfo(
        user_id=info["user_id"],
        container_id=info["container_id"],
        status=info["status"],
        created_at=info["created_at"],
        last_used=info["last_used"],
        execution_count=info["execution_count"],
        memory_usage_mb=info["memory_usage_mb"],
        cpu_percent=info["cpu_percent"],
    )


@app.post(
    "/sandbox/{user_id}/stop",
    tags=["Sandbox"],
    dependencies=[Depends(verify_api_key)],
)
async def stop_sandbox(user_id: str) -> dict:
    """Stop a user's sandbox (preserves files)."""
    manager = get_manager()
    success = await manager.destroy_sandbox(user_id)
    return {"status": "stopped" if success else "not_found"}


@app.post(
    "/sandbox/{user_id}/restart",
    response_model=SandboxInfo,
    tags=["Sandbox"],
    dependencies=[Depends(verify_api_key)],
)
async def restart_sandbox(user_id: str) -> SandboxInfo:
    """Restart a user's sandbox."""
    manager = get_manager()

    # Destroy existing
    await manager.destroy_sandbox(user_id)

    # Create new
    container = await manager.get_sandbox(user_id)
    if not container:
        raise HTTPException(
            status_code=503,
            detail="Failed to restart sandbox",
        )

    session = manager.sessions.get(user_id)
    return SandboxInfo(
        user_id=user_id,
        container_id=container.short_id,
        status="running",
        created_at=session.created_at,
        last_used=session.last_used,
        execution_count=session.execution_count,
    )


@app.delete(
    "/sandbox/{user_id}",
    tags=["Sandbox"],
    dependencies=[Depends(verify_api_key)],
)
async def delete_sandbox(user_id: str) -> dict:
    """Delete a user's sandbox (files are preserved on host)."""
    manager = get_manager()
    success = await manager.destroy_sandbox(user_id)
    return {"status": "deleted" if success else "not_found", "files_preserved": True}


# ============================================================================
# Code Execution Endpoints
# ============================================================================


def _result_to_response(result: ExecutionResult) -> ExecutionResponse:
    """Convert ExecutionResult to API response."""
    return ExecutionResponse(
        success=result.success,
        output=result.output,
        error=result.error,
        exit_code=result.exit_code,
        execution_time=result.execution_time,
    )


@app.post(
    "/sandbox/{user_id}/execute",
    response_model=ExecutionResponse,
    tags=["Execution"],
    dependencies=[Depends(verify_api_key)],
)
async def execute_code(user_id: str, request: ExecuteCodeRequest) -> ExecutionResponse:
    """Execute Python code in the sandbox."""
    manager = get_manager()
    result = await manager.execute_code(user_id, request.code, timeout=request.timeout)
    return _result_to_response(result)


@app.post(
    "/sandbox/{user_id}/shell",
    response_model=ExecutionResponse,
    tags=["Execution"],
    dependencies=[Depends(verify_api_key)],
)
async def run_shell(user_id: str, request: ShellCommandRequest) -> ExecutionResponse:
    """Run a shell command in the sandbox."""
    manager = get_manager()
    result = await manager.run_shell(user_id, request.command, timeout=request.timeout)
    return _result_to_response(result)


@app.post(
    "/sandbox/{user_id}/pip/install",
    response_model=ExecutionResponse,
    tags=["Execution"],
    dependencies=[Depends(verify_api_key)],
)
async def install_package(
    user_id: str, request: InstallPackageRequest
) -> ExecutionResponse:
    """Install a pip package in the sandbox."""
    manager = get_manager()
    result = await manager.install_package(
        user_id, request.package, timeout=request.timeout
    )
    return _result_to_response(result)


@app.get(
    "/sandbox/{user_id}/pip/list",
    response_model=ExecutionResponse,
    tags=["Execution"],
    dependencies=[Depends(verify_api_key)],
)
async def list_packages(user_id: str) -> ExecutionResponse:
    """List installed pip packages in the sandbox."""
    manager = get_manager()
    result = await manager.run_shell(user_id, "pip list", timeout=30)
    return _result_to_response(result)


# ============================================================================
# File Operation Endpoints
# ============================================================================


@app.get(
    "/sandbox/{user_id}/files",
    response_model=ExecutionResponse,
    tags=["Files"],
    dependencies=[Depends(verify_api_key)],
)
async def list_files(user_id: str, path: str = "/workspace") -> ExecutionResponse:
    """List files in a directory."""
    manager = get_manager()
    result = await manager.list_files(user_id, path)
    return _result_to_response(result)


@app.get(
    "/sandbox/{user_id}/file",
    tags=["Files"],
    dependencies=[Depends(verify_api_key)],
)
async def read_file(user_id: str, path: str) -> ReadFileResponse:
    """Read a file from the sandbox."""
    manager = get_manager()
    result = await manager.read_file(user_id, path)

    if not result.success:
        raise HTTPException(
            status_code=404,
            detail=result.error or "File not found",
        )

    # Try to detect if content is binary
    try:
        content = result.output
        encoding = "utf-8"
    except UnicodeDecodeError:
        content = base64.b64encode(result.output.encode("latin-1")).decode("ascii")
        encoding = "base64"

    return ReadFileResponse(
        path=path,
        content=content,
        encoding=encoding,
        size=len(result.output),
    )


@app.post(
    "/sandbox/{user_id}/file",
    response_model=ExecutionResponse,
    tags=["Files"],
    dependencies=[Depends(verify_api_key)],
)
async def write_file(user_id: str, request: WriteFileRequest) -> ExecutionResponse:
    """Write a file to the sandbox."""
    manager = get_manager()

    content: str | bytes = request.content
    if request.encoding == "base64":
        content = base64.b64decode(request.content)

    result = await manager.write_file(user_id, request.path, content)
    return _result_to_response(result)


@app.delete(
    "/sandbox/{user_id}/file",
    response_model=ExecutionResponse,
    tags=["Files"],
    dependencies=[Depends(verify_api_key)],
)
async def delete_file(user_id: str, path: str) -> ExecutionResponse:
    """Delete a file from the sandbox."""
    manager = get_manager()
    result = await manager.run_shell(user_id, f"rm -f '{path}'", timeout=10)
    return _result_to_response(result)


@app.post(
    "/sandbox/{user_id}/unzip",
    response_model=ExecutionResponse,
    tags=["Files"],
    dependencies=[Depends(verify_api_key)],
)
async def unzip_file(user_id: str, request: UnzipRequest) -> ExecutionResponse:
    """Extract an archive file."""
    manager = get_manager()
    result = await manager.unzip_file(user_id, request.path, request.destination)
    return _result_to_response(result)


# ============================================================================
# Error Handlers
# ============================================================================


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Handle unexpected exceptions."""
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


# ============================================================================
# CLI Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    from .config import API_HOST, API_PORT

    uvicorn.run(app, host=API_HOST, port=API_PORT)
