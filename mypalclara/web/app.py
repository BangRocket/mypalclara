"""FastAPI application factory for MyPalClara web interface."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from mypalclara.web.config import get_web_config

logger = logging.getLogger("web")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    from db.connection import init_db

    logger.info("Initializing database...")
    init_db()

    # Start the web chat adapter (connects to gateway)
    from mypalclara.web.chat.adapter import web_chat_adapter

    try:
        await web_chat_adapter.start_background()
        logger.info("Web chat adapter connected to gateway")
    except Exception as e:
        logger.warning(f"Web chat adapter failed to connect (chat disabled): {e}")

    yield

    # Shutdown
    try:
        await web_chat_adapter.stop()
    except Exception:
        pass


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    config = get_web_config()

    app = FastAPI(
        title="MyPalClara",
        description="Clara's Web Interface",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Rate limiting (added before CORS so it runs after CORS in the middleware stack)
    from mypalclara.web.middleware import RateLimitMiddleware

    app.add_middleware(RateLimitMiddleware, requests_per_minute=120, burst=30)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API routes
    from mypalclara.web.api.router import api_router
    from mypalclara.web.auth.oauth import router as auth_router
    from mypalclara.web.chat.websocket import router as chat_router

    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    app.include_router(api_router, prefix="/api/v1")
    app.include_router(chat_router, tags=["chat"])

    # Serve frontend static files in production
    if config.static_dir:
        static_path = Path(config.static_dir)
        if static_path.is_dir():
            app.mount("/", StaticFiles(directory=str(static_path), html=True), name="static")

    return app
