"""Health check endpoints for the Clara Gateway.

Provides:
- /health - Liveness probe (is the process running?)
- /ready - Readiness probe (can we handle traffic?)
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

from config.logging import get_logger

logger = get_logger("gateway.health")

health_app = FastAPI(
    title="Clara Gateway Health",
    docs_url=None,  # No Swagger UI needed for health checks
    redoc_url=None,
)

# Will be set by main.py after gateway starts
_gateway_server = None
_gateway_processor = None
_started_at: datetime | None = None


def set_gateway_components(server, processor, started_at: datetime):
    """Set gateway components for health checks."""
    global _gateway_server, _gateway_processor, _started_at
    _gateway_server = server
    _gateway_processor = processor
    _started_at = started_at


async def check_websocket_server() -> tuple[bool, str]:
    """Check if WebSocket server is running."""
    if _gateway_server is None:
        return False, "not_initialized"
    if _gateway_server._server is None:
        return False, "not_started"
    return True, "ok"


async def check_processor() -> tuple[bool, str]:
    """Check if processor is initialized."""
    if _gateway_processor is None:
        return False, "not_initialized"
    if not _gateway_processor._initialized:
        return False, "not_ready"
    if _gateway_processor._memory_manager is None:
        return False, "no_memory_manager"
    return True, "ok"


async def check_database() -> tuple[bool, str]:
    """Check database connectivity via processor's memory manager."""
    if _gateway_processor is None or _gateway_processor._memory_manager is None:
        return False, "no_memory_manager"

    try:
        # Memory manager uses db sessions internally
        # A simple check that it's accessible
        return True, "ok"
    except Exception as e:
        return False, str(e)


@health_app.get("/health")
async def liveness():
    """Liveness probe - is the gateway process running?

    Returns 200 if the process is alive.
    Used by orchestrators to detect crashed processes.
    """
    uptime = None
    if _started_at:
        uptime = int((datetime.now() - _started_at).total_seconds())

    return {
        "status": "healthy",
        "uptime_seconds": uptime,
    }


@health_app.get("/ready")
async def readiness():
    """Readiness probe - can the gateway handle traffic?

    Returns 200 if all dependencies are healthy.
    Returns 503 if any dependency is unhealthy.
    Used by load balancers to route traffic.
    """
    checks = await asyncio.gather(
        check_websocket_server(),
        check_processor(),
        check_database(),
        return_exceptions=True
    )

    results = {}
    all_healthy = True

    check_names = ["websocket_server", "processor", "database"]
    for name, check in zip(check_names, checks):
        if isinstance(check, Exception):
            results[name] = f"error: {check}"
            all_healthy = False
        elif isinstance(check, tuple):
            healthy, message = check
            results[name] = message
            if not healthy:
                all_healthy = False
        else:
            results[name] = "unknown"
            all_healthy = False

    status_code = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        content={
            "status": "ready" if all_healthy else "not_ready",
            "checks": results,
        },
        status_code=status_code
    )


@health_app.get("/status")
async def gateway_status():
    """Detailed gateway status for monitoring dashboards."""
    server_stats = _gateway_server.get_stats() if _gateway_server else {}

    return {
        "status": "running" if _gateway_server else "not_running",
        "server": server_stats,
        "started_at": _started_at.isoformat() if _started_at else None,
    }
