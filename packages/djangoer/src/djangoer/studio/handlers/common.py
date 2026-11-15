"""What the path operations share: the Studio a request is asked of, and the problems they
name in the OpenAPI document."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.responses import StreamingResponse

from .. import contract
from ..state import State


def _state(request: Request) -> State:
    return request.app.state.studio


# The Studio a request is asked of: `state: StudioState` in a path operation.
StudioState = Annotated[State, Depends(_state)]

# What FastAPI takes as the `responses` of a path operation.
Responses = dict[int | str, dict[str, Any]]


def _problem(status: int, model: type[contract.Problem], description: str) -> Responses:
    return {
        status: {
            "description": description,
            "content": {
                "application/problem+json": {
                    "schema": {"$ref": f"#/components/schemas/{model.__name__}"}
                }
            },
        }
    }


# The problems a path operation can answer with, for the OpenAPI document.
NOT_FOUND = _problem(404, contract.NotFoundProblem, "The model is not in the schema.")
INVALID = _problem(
    422, contract.ValidationProblem, "The request, or what the database made of it, is not valid."
)
UNAVAILABLE = _problem(503, contract.ServiceUnavailableProblem, "The database cannot be reached.")


def server_sent_events(events: AsyncIterator[tuple[str, object]]) -> StreamingResponse:
    """A stream of (name, data) events, written as `text/event-stream`."""

    async def frames() -> AsyncIterator[bytes]:
        # How long a listener waits before it connects again. The server restarts when the
        # project's code changes, and a second is how soon the page should be told what changed.
        yield b"retry: 1000\n\n"
        async for name, data in events:
            yield f"event: {name}\ndata: {data}\n\n".encode()

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
