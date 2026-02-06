"""Tests for web rate limiting middleware."""

from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from mypalclara.web.middleware import RateLimitMiddleware


def homepage(request: Request) -> JSONResponse:
    return JSONResponse({"ok": True})


def make_app(rpm: int = 10, burst: int = 3) -> Starlette:
    """Create a test Starlette app with rate limiting."""
    app = Starlette(
        routes=[
            Route("/api/test", homepage),
            Route("/static/file", homepage),
        ],
    )
    app.add_middleware(RateLimitMiddleware, requests_per_minute=rpm, burst=burst)
    return app


class TestRateLimitMiddleware:
    """Tests for rate limit middleware."""

    def test_normal_request_passes(self):
        """Single request passes through."""
        client = TestClient(make_app())
        resp = client.get("/api/test")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_static_not_rate_limited(self):
        """Static file paths are not rate limited."""
        client = TestClient(make_app(rpm=1, burst=1))
        # First API request
        resp1 = client.get("/api/test")
        assert resp1.status_code == 200
        # Static requests should pass regardless
        for _ in range(10):
            resp = client.get("/static/file")
            assert resp.status_code == 200

    def test_burst_limit(self):
        """Exceeding burst limit returns 429."""
        client = TestClient(make_app(rpm=100, burst=2))
        # First two should pass
        assert client.get("/api/test").status_code == 200
        assert client.get("/api/test").status_code == 200
        # Third in same second should be limited
        resp = client.get("/api/test")
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers

    def test_rpm_limit(self):
        """Exceeding RPM limit returns 429."""
        client = TestClient(make_app(rpm=3, burst=100))
        for _ in range(3):
            assert client.get("/api/test").status_code == 200
        resp = client.get("/api/test")
        assert resp.status_code == 429
