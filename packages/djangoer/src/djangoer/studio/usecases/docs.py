"""What the Docs page asks for."""

from __future__ import annotations

from .. import inputs
from ..services import DocsService


def read_docs(input: inputs.OnDatabase):
    return DocsService.read(input)
