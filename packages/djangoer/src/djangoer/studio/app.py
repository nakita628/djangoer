"""The FastAPI app of Studio: the API under `/api`, the built client everywhere else."""

from __future__ import annotations

import mimetypes
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, get_args

from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from .. import __version__
from . import contract
from .handlers import client, db, docs, export, problems, schema
from .state import State

STATIC_DIR = Path(__file__).parent / "static"
LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})

NOT_BUILT = """<!doctype html>
<meta charset="utf-8">
<title>Djangoer Studio</title>
<body style="font: 16px/1.6 system-ui; max-width: 40rem; margin: 4rem auto; padding: 0 1rem">
<h1>Djangoer Studio</h1>
<p>The API is running, but the Studio client is not built in this checkout.</p>
<pre>pnpm install &amp;&amp; pnpm build</pre>
<p>A release from PyPI ships it already built.</p>
"""


class Guard:
    """What a server on localhost has to refuse, before a request reaches the app.

    A page of another site can make the browser send requests here. It cannot read the answers,
    but a write does its harm on arrival, so: only a request addressed to this host is served
    (no DNS rebinding), and a body is taken only as JSON, which another origin cannot send
    without a preflight this server does not grant.
    """

    def __init__(self, app: ASGIApp, *, bound_host: str):
        self.app = app
        self.check_host = bound_host in LOOPBACK

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {
            key.decode("latin-1"): value.decode("latin-1") for key, value in scope["headers"]
        }
        host = headers.get("host", "")
        # `[::1]:5555` keeps its brackets; `localhost:5555` loses its port.
        name = host.split("]")[0] + "]" if host.startswith("[") else host.rsplit(":", 1)[0]
        if self.check_host and name not in LOOPBACK:
            await JSONResponse({"detail": "Forbidden host"}, 403)(scope, receive, send)
            return
        has_body = int(headers.get("content-length") or 0) > 0 or "transfer-encoding" in headers
        content_type = headers.get("content-type", "").split(";")[0].strip().lower()
        if (
            scope["method"] not in ("GET", "HEAD")
            and has_body
            and content_type != "application/json"
        ):
            await JSONResponse({"detail": "Unsupported Media Type"}, 415)(scope, receive, send)
            return
        await self.app(scope, receive, send)


def _static(static_dir: Path, path: str) -> Response:
    """A file of the built client; for a client-side route, the entry page."""
    index = static_dir / "index.html"
    if not index.is_file():
        return HTMLResponse(NOT_BUILT)
    target = (static_dir / path).resolve()
    inside = static_dir.resolve() in target.parents
    if not path or not inside or not target.is_file():
        if path and "." in path.rsplit("/", 1)[-1]:
            return PlainTextResponse("Not Found", 404)
        target = index
    media_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    # Built assets carry a hash in their name; the entry page must always be fresh.
    hashed = target != index and "/assets/" in target.as_posix()
    cache = "public, max-age=31536000, immutable" if hashed else "no-cache"
    return Response(target.read_bytes(), media_type=media_type, headers={"Cache-Control": cache})


def create_api(state: State | None) -> FastAPI:
    """The API alone, as it is mounted under `/api`: its paths are `/schema`, `/db/rows/…`, and
    its OpenAPI document says so, with `/api` as the server."""
    api = FastAPI(
        title="Djangoer Studio",
        version=__version__,
        description="The API behind Djangoer Studio: the schema, the database, the Django ORM playground and the docs.",
        openapi_url="/openapi.json",
        docs_url="/reference",
        redoc_url=None,
    )
    api.state.studio = state
    problems.register(api)

    @api.middleware("http")
    async def loaded(request: Request, call_next: Callable[[Request], Awaitable[Response]]):
        """A project that does not load has a schema to show (the reason) and nothing else."""
        failure = state.failure if state is not None else None
        if failure is None or request.url.path.startswith("/api/schema"):
            return await call_next(request)
        return problems.answer(
            contract.ServiceUnavailableProblem(
                detail=f"The project does not load: {type(failure).__name__}: {failure}",
                instance=request.url.path,
            )
        )

    for module in (schema, db, client, docs, export):
        api.include_router(module.router)
    api.openapi = lambda: _openapi(api)  # type: ignore[method-assign]
    return api


def create_app(
    state: State | None, *, static_dir: Path | None = None, bound_host: str = "127.0.0.1"
) -> FastAPI:
    """The app for one project and one database: the API under `/api`, the built client
    everywhere else. Django must be set up already."""
    served = static_dir or STATIC_DIR
    app = FastAPI(title="Djangoer Studio", openapi_url=None, docs_url=None, redoc_url=None)
    app.mount("/api", create_api(state))

    @app.get("/{path:path}", include_in_schema=False)
    def client_files(path: str) -> Response:
        return _static(served, path)

    app.add_middleware(Guard, bound_host=bound_host)
    return app


def _openapi(app: FastAPI) -> dict[str, Any]:
    """The OpenAPI document, with the problems the routes name by reference among its schemas."""
    if app.openapi_schema is None:
        document = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            # One schema per model, whether it is read or written: the names the client's types take.
            separate_input_output_schemas=False,
            servers=[{"url": "/api"}],
        )
        schemas = document.setdefault("components", {}).setdefault("schemas", {})
        for model in get_args(contract.AnyProblem):
            schema = model.model_json_schema(
                by_alias=True, ref_template="#/components/schemas/{model}"
            )
            schemas.update(schema.pop("$defs", {}))
            schemas[model.__name__] = schema
        app.openapi_schema = document
    return app.openapi_schema


def openapi_document() -> dict[str, Any]:
    """The OpenAPI document of the API, without a project: the client's types are generated
    from it (packages/studio/openapi.json)."""
    return create_api(None).openapi()
