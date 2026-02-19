"""Entry point for the Clara web interface."""

import os

import uvicorn

from mypalclara.web.config import get_web_config


def main():
    config = get_web_config()
    reload = os.getenv("WEB_RELOAD", "false").lower() in ("true", "1", "yes")
    uvicorn.run(
        "mypalclara.web.app:create_app",
        factory=True,
        host=config.host,
        port=config.port,
        reload=reload,
    )


if __name__ == "__main__":
    main()
