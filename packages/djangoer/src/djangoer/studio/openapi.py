"""`python -m djangoer.studio.openapi`: print the OpenAPI document of the API.

The Studio client's types and hooks are generated from it (`just openapi`), so the document is
kept in the repository, and a test fails when it no longer matches the server.
"""

from __future__ import annotations

import json

from .app import openapi_document


def render() -> str:
    return json.dumps(openapi_document(), indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    print(render(), end="")
