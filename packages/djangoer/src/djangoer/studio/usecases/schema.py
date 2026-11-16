"""What the Schema and models.py pages ask for."""

from __future__ import annotations

from .. import inputs
from ..services import SchemaService
from ..state import State


def read_schema(input: State):
    """The schema as last read, or the reason there is none."""
    return SchemaService.read(input)


def reload_schema(input: State):
    """Read the models again; whoever listens to the events is told."""
    return SchemaService.reload(input)


def watch_schema(input: State):
    """The events of the schema, for as long as someone listens. The server restarts when the
    project's code changes, so a listener that reconnects is told `ready` again."""
    return SchemaService.events(input)


def write_schema_file(input: inputs.WriteFile):
    """Write a model file back as it was edited. The server starts again when the file
    changes, so the schema that follows is read from what was written."""
    return SchemaService.write(input)
