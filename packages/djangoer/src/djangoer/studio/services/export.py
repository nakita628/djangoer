"""The schema as a file to save: a diagram or the docs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .. import inputs
from ..domain import export
from ..errors import ExportError
from .effect import effect


class Download(BaseModel):
    """A file as it is handed to the browser. Not part of the API's contract: it is the body
    of a download, not JSON."""

    model_config = ConfigDict(frozen=True)

    name: str
    media_type: str
    content: bytes


def download(input: inputs.ExportFile):
    return effect(Download, (ExportError,), lambda: export.download(input))
