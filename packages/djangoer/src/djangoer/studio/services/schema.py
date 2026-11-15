"""The schema: read from the state, or re-read from the project's models."""

from __future__ import annotations

import asyncio
import time

from returns.result import Success

from ..state import State


def read(input: State):
    return Success(input.snapshot)


def reload(input: State):
    return Success(input.reload())


EVENT_PING_SECONDS = 15
EVENT_POLL_SECONDS = 0.25


async def events(input: State):
    """What happens to the schema, as it happens: `ready` at once, `change` after every
    reload, and `ping` when 15 seconds pass in silence, to keep a connection open. Each event
    is its name and its data."""
    seen = input.version
    yield "ready", input.snapshot.updated_at
    quiet_since = time.monotonic()
    while True:
        await asyncio.sleep(EVENT_POLL_SECONDS)
        if input.version != seen:
            seen = input.version
            quiet_since = time.monotonic()
            yield "change", input.snapshot.updated_at
        elif time.monotonic() - quiet_since >= EVENT_PING_SECONDS:
            quiet_since = time.monotonic()
            yield "ping", int(time.time())
