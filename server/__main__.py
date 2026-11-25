"""``python -m server`` binds the host and port from settings."""

import uvicorn

from server.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "server.app:create_app",
        factory=True,
        host=settings.http_host,
        port=settings.http_port,
    )


if __name__ == "__main__":
    main()
