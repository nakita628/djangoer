from pathlib import Path

import pytest

from djangoer.studio.openapi import render

DOCUMENT = Path(__file__).parents[2] / "studio" / "openapi.json"


def test_the_committed_document_is_the_one_the_server_writes():
    """The client's types and hooks are generated from packages/studio/openapi.json."""
    if not DOCUMENT.is_file():
        pytest.skip("packages/studio is not in this checkout")
    assert DOCUMENT.read_text(encoding="utf-8") == render(), (
        "The API changed: run `uv run just openapi` to rewrite openapi.json and the client's types."
    )


def test_every_operation_names_its_problems(api):
    status, document = api("GET", "/api/openapi.json")
    assert status == 200
    assert document["servers"] == [{"url": "/api"}]
    rows = document["paths"]["/db/rows/{modelName}"]["get"]
    assert rows["operationId"] == "readRows"
    assert set(rows["responses"]) == {"200", "404", "422", "503"}
    problem = rows["responses"]["422"]["content"]["application/problem+json"]["schema"]
    assert problem == {"$ref": "#/components/schemas/ValidationProblem"}
    assert "ValidationProblem" in document["components"]["schemas"]
    # The event stream is read with EventSource: it has no place among the generated hooks.
    assert "/schema/events" not in document["paths"]
