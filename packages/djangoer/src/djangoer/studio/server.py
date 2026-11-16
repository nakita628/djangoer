"""Serving the app: uvicorn, on a socket bound before it starts."""

from __future__ import annotations

import socket
from pathlib import Path

import uvicorn

from .app import create_app
from .brands import Alias
from .state import State


class StudioServer:
    """A Studio server ready to `serve_forever()`.

    The socket is bound here, not by uvicorn: a port that is taken fails at once with an
    `OSError`, and `server_address` is known before the first request, also for port 0.
    """

    def __init__(self, app, host: str, port: int, *, quiet: bool):
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        self.socket = socket.socket(family, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.socket.bind((host, port))
        except OSError:
            self.socket.close()
            raise
        self.server_address = self.socket.getsockname()
        self.server = uvicorn.Server(
            uvicorn.Config(
                app,
                log_level="warning",
                access_log=not quiet,
                # The event stream never ends by itself: do not wait for it when stopping.
                timeout_graceful_shutdown=1,
                server_header=False,
            )
        )

    def serve_forever(self) -> None:
        self.server.run(sockets=[self.socket])

    def shutdown(self) -> None:
        self.server.should_exit = True

    def server_close(self) -> None:
        self.socket.close()


def create_server(
    host: str = "127.0.0.1",
    port: int = 5555,
    *,
    database: str = "default",
    root: Path | None = None,
    static_dir: Path | None = None,
    quiet: bool = True,
    failure: BaseException | None = None,
) -> StudioServer:
    """A server for the project in `root` and one of its databases. Django must be set up, or
    `failure` say why it could not be: the server then answers with that alone."""
    state = State(Alias(database), root or Path.cwd(), failure)
    app = create_app(state, static_dir=static_dir, bound_host=host)
    return StudioServer(app, host, port, quiet=quiet)
