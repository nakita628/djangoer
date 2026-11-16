"""Writing a model file back: the one thing Studio changes on disk."""

from __future__ import annotations

from typing import Any

from returns.result import Failure, Result

from ..errors import FileWriteError, StudioError, UnknownFileError
from ..inputs import WriteFile
from .attempt import attempt


def write(input: WriteFile) -> Result[dict[str, Any], StudioError]:
    """Write one of the project's model files. Only a path Studio lists can be written, so a
    request cannot name a file elsewhere on the disk."""
    if input.path not in input.files:
        return Failure(UnknownFileError(input.path))
    target = input.root / input.path

    def save() -> dict[str, Any]:
        target.write_text(input.content, encoding="utf-8")
        return {"path": input.path, "content": input.content}

    return attempt(save, (OSError,), lambda error: FileWriteError(input.path, str(error)))
