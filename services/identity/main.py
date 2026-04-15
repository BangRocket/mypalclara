"""Identity service entrypoint."""

from __future__ import annotations

import uvicorn

from identity.config import HOST, PORT
from identity.app import create_app
from identity.db import init_db

app = create_app()


def main():
    init_db()
    uvicorn.run("identity.main:app", host=HOST, port=PORT, reload=False)


if __name__ == "__main__":
    main()
