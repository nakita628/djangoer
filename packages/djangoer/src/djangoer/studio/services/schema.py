"""The schema: read from the state, or re-read from the project's models."""

from __future__ import annotations

import asyncio
import time

from returns.result import Success

from .. import contract, inputs
from ..domain import files, source
from ..domain import preview as previews
from ..errors import FileWriteError, PreviewError, UnknownFileError
from ..state import State
from .effect import effect, reading


def read(input: State):
    return Success(input.snapshot)


def reload(input: State):
    return Success(input.reload())


def write(input: inputs.WriteFile):
    return effect(
        contract.SchemaFile, (UnknownFileError, FileWriteError), lambda: files.write(input)
    )


def complete(input: inputs.SourceAt):
    return reading(contract.ClientCompletions, lambda: source.complete(input))


def hover(input: inputs.SourceAt):
    return reading(contract.ClientHover, lambda: source.hover(input))


def check(input: inputs.SourceText):
    return reading(contract.ClientTypeDiagnostics, lambda: source.check(input))


def preview(input: inputs.PreviewSource):
    return effect(contract.Schema, (PreviewError,), lambda: previews.preview(input))


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
