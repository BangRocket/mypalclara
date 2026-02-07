"""Rate limiting middleware for the Clara web API."""

from __future__ import annotations

import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory sliding window rate limiter.

    Limits per-IP request rate on API endpoints.
    Does not limit static file serving or WebSocket upgrades.
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 120,
        burst: int = 30,
    ) -> None:
        super().__init__(app)
        self.rpm = requests_per_minute
        self.burst = burst
        self._windows: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Only rate-limit API and auth endpoints
        if not (path.startswith("/api/") or path.startswith("/auth/")):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = self._windows[client_ip]

        # Remove timestamps older than 60s
        cutoff = now - 60.0
        window[:] = [t for t in window if t > cutoff]

        # Check burst (requests in last 1s)
        one_sec_ago = now - 1.0
        recent = sum(1 for t in window if t > one_sec_ago)
        if recent >= self.burst:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."},
                headers={"Retry-After": "1"},
            )

        # Check sustained rate
        if len(window) >= self.rpm:
            oldest = window[0]
            retry_after = int(60 - (now - oldest)) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={"Retry-After": str(retry_after)},
            )

        window.append(now)
        return await call_next(request)
