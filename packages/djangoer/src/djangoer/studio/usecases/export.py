"""What the export buttons of the Schema page ask for."""

from __future__ import annotations

from .. import inputs
from ..services import ExportService


def download_file(input: inputs.ExportFile):
    """The diagram or the docs of the project's models, as a file to save."""
    return ExportService.download(input)
