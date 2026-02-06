"""Entry point for the Clara web interface."""

import uvicorn

from mypalclara.web.config import get_web_config


def main():
    config = get_web_config()
    uvicorn.run(
        "mypalclara.web.app:create_app",
        factory=True,
        host=config.host,
        port=config.port,
        reload=True,
    )


if __name__ == "__main__":
    main()
