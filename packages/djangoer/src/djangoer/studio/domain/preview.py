"""The schema of a model file as it is being edited: what the diagram would show if it were saved.

The text is loaded in a process of its own (preview_worker.py), with the project's settings, so
the project Studio serves, and the file on disk, are not touched. A text that does not load
answers with why; the page keeps the last diagram that did.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

from returns.result import Failure, Result, Success

from ..errors import PreviewError, StudioError
from ..inputs import PreviewSource
from .attempt import attempt

# Django starts in well under a second; a text that takes longer is not a preview to wait for.
TIMEOUT_SECONDS = 15


def _run(input: PreviewSource) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "-m", "djangoer.studio.preview_worker"],
        input=json.dumps({"path": input.path, "content": input.content, "alias": input.alias}),
        capture_output=True,
        text=True,
        cwd=input.root,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        timeout=TIMEOUT_SECONDS,
        check=False,
    )
    lines = completed.stdout.strip().splitlines()
    if completed.returncode != 0 or not lines:
        reason = completed.stderr.strip().splitlines()
        return {"error": reason[-1] if reason else "The preview could not be built."}
    return json.loads(lines[-1])


def preview(input: PreviewSource) -> Result[dict[str, Any], StudioError]:
    def ran(answer: dict[str, Any]) -> Result[dict[str, Any], StudioError]:
        if "schema" in answer:
            return Success(answer["schema"])
        return Failure(PreviewError(answer.get("error", "The preview could not be built.")))

    return attempt(
        lambda: _run(input),
        (OSError, subprocess.SubprocessError, ValueError),
        lambda error: PreviewError(f"The preview could not be built: {error}"),
    ).bind(ran)
