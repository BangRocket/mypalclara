"""Entry point for the Clara web interface."""

import os

import uvicorn

from mypalclara.web.config import get_web_config


def main():
    config = get_web_config()
    # Reload only in explicit dev mode, not when managed by the gateway
    reload = os.getenv("WEB_RELOAD", "").lower() in ("1", "true", "yes")
    uvicorn.run(
        "mypalclara.web.app:create_app",
        factory=True,
        host=config.host,
        port=config.port,
        reload=reload,
    )


if __name__ == "__main__":
    main()
