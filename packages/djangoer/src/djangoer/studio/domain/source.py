"""Inference for a model file while it is edited: what can be typed next, what a name is, and
where the syntax breaks.

The reading is jedi's, which follows Python as an editor does: `Post.objects.filter(...).first()`
is a Post, and its fields complete. jedi is an optional dependency (`djangoer[inference]`):
without it every answer here is empty, and the editor is an editor without suggestions.
"""

from __future__ import annotations

import importlib
import threading
from typing import Any

from ..inputs import SourceAt, SourceText

# jedi keeps caches of its own that it does not guard: one request reads at a time.
_LOCK = threading.Lock()
MAX_COMPLETIONS = 200
# jedi's kinds of names, as the kinds the editor has icons for.
KINDS = {
    "module": "module",
    "class": "class",
    "instance": "variable",
    "function": "function",
    "param": "variable",
    "statement": "variable",
    "keyword": "keyword",
    "property": "property",
    "path": "module",
}


def _jedi() -> Any | None:
    try:
        return importlib.import_module("jedi")
    except ImportError:
        return None


def _script(input: SourceText) -> Any | None:
    jedi = _jedi()
    if jedi is None:
        return None
    return jedi.Script(
        code=input.content,
        path=str(input.root / input.path),
        project=jedi.Project(str(input.root)),
    )


def position(text: str, offset: int) -> tuple[int, int]:
    """A character offset as jedi's position: a line from 1, a column from 0."""
    before = text[: max(0, min(offset, len(text)))]
    return before.count("\n") + 1, len(before) - (before.rfind("\n") + 1)


def offset_of(text: str, line: int, column: int) -> int:
    lines = text.split("\n")
    return sum(len(entry) + 1 for entry in lines[: line - 1]) + column


def complete(input: SourceAt) -> dict[str, Any]:
    """`ClientCompletions`: what can be typed at the cursor."""
    with _LOCK:
        script = _script(input)
        if script is None:
            return {"items": []}
        line, column = position(input.content, input.offset)
        try:
            names = script.complete(line, column)[:MAX_COMPLETIONS]
        except Exception:  # noqa: BLE001 - jedi on half-typed code: no suggestion is the answer
            return {"items": []}
        return {
            "items": [
                {
                    "label": name.name,
                    "kind": KINDS.get(name.type, "variable"),
                    # jedi's own order: what fits the place first.
                    "sortText": f"{index:04d}",
                    "insertText": None,
                }
                for index, name in enumerate(names)
            ]
        }


def _describe(name: Any) -> str | None:
    signatures = [signature.to_string() for signature in name.get_signatures()]
    head = "\n".join(signatures) or name.description
    documentation = name.docstring(raw=True)
    parts = [f"```python\n{head}\n```"] if head else []
    if documentation:
        parts.append(documentation)
    return "\n\n".join(parts) or None


def hover(input: SourceAt) -> dict[str, Any]:
    """`ClientHover`: the name under the cursor, with its signature and its docstring."""
    empty = {"contents": None, "range": None}
    with _LOCK:
        script = _script(input)
        if script is None:
            return empty
        line, column = position(input.content, input.offset)
        try:
            names = script.help(line, column)
            contents = _describe(names[0]) if names else None
        except Exception:  # noqa: BLE001 - jedi on half-typed code: nothing to say
            return empty
        return {"contents": contents, "range": None}


def check(input: SourceText) -> dict[str, Any]:
    """`ClientTypeDiagnostics`: where the file's syntax breaks, as it is typed."""
    with _LOCK:
        script = _script(input)
        if script is None:
            return {"diagnostics": []}
        try:
            errors = script.get_syntax_errors()
        except Exception:  # noqa: BLE001
            return {"diagnostics": []}
        diagnostics = []
        for error in errors:
            start = offset_of(input.content, error.line, error.column)
            end = offset_of(input.content, error.until_line, error.until_column)
            diagnostics.append(
                {
                    "message": error.get_message(),
                    "severity": "error",
                    "range": {"start": start, "end": max(end, start + 1)},
                }
            )
        return {"diagnostics": diagnostics}
