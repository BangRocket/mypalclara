"""Entry point for the Clara web interface."""

import uvicorn

from clara_core.config import get_settings
from mypalclara.web.config import get_web_config


def main():
    config = get_web_config()
    # Reload only in explicit dev mode, not when managed by the gateway
    reload = get_settings().web.reload
    uvicorn.run(
        "mypalclara.web.app:create_app",
        factory=True,
        host=config.host,
        port=config.port,
        reload=reload,
    )


if __name__ == "__main__":
    main()
