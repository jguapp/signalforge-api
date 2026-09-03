from __future__ import annotations

from wsgiref.simple_server import make_server

from .bootstrap import create_application
from .config import Config


def main() -> None:
    config = Config.from_environment()
    application = create_application(config=config)
    with make_server(config.host, config.port, application) as server:
        print(f"SignalForge listening on http://{config.host}:{config.port}")
        server.serve_forever()


if __name__ == "__main__":
    main()

