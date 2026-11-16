"""`python -m djangoer.studio.preview_worker`: the schema of a project with one model file as it
is being edited, not as it is on disk.

Run in a process of its own (domain/preview.py), so the project Studio serves is not touched:
the edited text is what `import` reads for that file, and what `inspect` reads for its lines.
Reads {path, content, alias} as JSON on stdin; writes {"schema": ...} or {"error": ...}.
"""

from __future__ import annotations

import importlib.machinery
import json
import linecache
import os
import sys
from pathlib import Path
from typing import Any


class EditedLoader(importlib.machinery.SourceFileLoader):
    """Loads the edited file from the text it was handed, never from disk or a cached .pyc."""

    content = ""

    def get_code(self, fullname: str) -> Any:
        return compile(self.content, self.path, "exec", dont_inherit=True)


class EditedFinder:
    """Finds modules as Python does, and hands the edited file to `EditedLoader`."""

    def __init__(self, target: str, content: str):
        self.target = target
        self.content = content

    def find_spec(self, fullname: str, path: Any = None, target: Any = None) -> Any:
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.origin is None or os.path.realpath(spec.origin) != self.target:
            return spec
        loader = EditedLoader(fullname, spec.origin)
        loader.content = self.content
        spec.loader = loader
        return spec


def main() -> int:
    request = json.load(sys.stdin)
    root = Path.cwd()
    target = os.path.realpath(root / request["path"])
    content: str = request["content"]
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root))
    sys.meta_path.insert(0, EditedFinder(target, content))
    # `inspect.getsourcelines` reads through linecache: the edited lines, so a class is located
    # where it is in the text being edited. An entry with no mtime is never checked against disk.
    lines = content.splitlines(keepends=True)
    linecache.cache[target] = (len(content), None, lines, target)
    try:
        import django

        django.setup()
        from djangoer.studio.domain.schema import build_schema

        schema = build_schema(request["alias"], root)
    except Exception as error:  # noqa: BLE001 - what stops the edited text from loading is the answer
        print(json.dumps({"error": f"{type(error).__name__}: {error}"}))
        return 0
    print(json.dumps({"schema": schema}, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
