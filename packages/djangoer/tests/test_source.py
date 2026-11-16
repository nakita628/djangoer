from pathlib import Path

from djangoer.studio import inputs
from djangoer.studio.domain import source

ROOT = Path(__file__).parent
PATH = "project/shop/models.py"
TEXT = (ROOT / PATH).read_text()


def labels(text: str) -> list[str]:
    at = inputs.SourceAt(path=PATH, content=text, offset=len(text), root=ROOT)
    return [item["label"] for item in source.complete(at)["items"]]


def test_completion_follows_python_as_an_editor_does():
    assert "CharField" in labels(TEXT + "\n\nfield = models.Cha")
    # `first()` on a queryset of Order is an Order: its fields complete.
    inferred = (
        TEXT
        + "\n\ndef latest():\n    order = Order.objects.filter(paid=True).first()\n    return order.no"
    )
    assert labels(inferred) == ["note"]
    assert labels(TEXT + "\n\nvalue = Customer.objects.fil")[0] == "filter"


def test_hover_describes_the_name_under_the_cursor():
    offset = TEXT.index("CharField(max_length=100)") + 3
    at = inputs.SourceAt(path=PATH, content=TEXT, offset=offset, root=ROOT)
    contents = source.hover(at)["contents"]
    assert contents.startswith("```python\nCharField(")
    # A blank line names nothing.
    blank = TEXT.index("\n\n\n") + 1
    nowhere = inputs.SourceAt(path=PATH, content=TEXT, offset=blank, root=ROOT)
    assert source.hover(nowhere) == {"contents": None, "range": None}


def test_check_finds_where_the_syntax_breaks():
    whole = inputs.SourceText(path=PATH, content=TEXT, root=ROOT)
    assert source.check(whole) == {"diagnostics": []}
    broken = TEXT + "\n\nclass Broken(:\n    pass\n"
    diagnostics = source.check(inputs.SourceText(path=PATH, content=broken, root=ROOT))[
        "diagnostics"
    ]
    assert diagnostics[0]["severity"] == "error"
    assert diagnostics[0]["message"].startswith("SyntaxError")
    start = diagnostics[0]["range"]["start"]
    assert broken[start] == ":"


def test_without_jedi_the_editor_has_no_suggestions_and_no_errors(monkeypatch):
    monkeypatch.setattr(source, "_jedi", lambda: None)
    at = inputs.SourceAt(
        path=PATH, content=TEXT + "\n\nfield = models.Cha", offset=len(TEXT) + 19, root=ROOT
    )
    assert source.complete(at) == {"items": []}
    assert source.hover(at) == {"contents": None, "range": None}
    assert source.check(at) == {"diagnostics": []}


def test_the_editor_asks_through_the_api(api):
    text = TEXT + "\n\nfield = models.Cha"
    status, body = api(
        "POST", "/api/schema/complete", {"path": PATH, "content": text, "offset": len(text)}
    )
    assert status == 200
    assert "CharField" in [item["label"] for item in body["items"]]
    status, body = api("POST", "/api/schema/check", {"path": PATH, "content": "class A(:\n"})
    assert status == 200
    assert body["diagnostics"][0]["severity"] == "error"
    status, _body = api("POST", "/api/schema/hover", {"path": PATH, "content": text, "offset": -1})
    assert status == 422


def test_preview_is_the_schema_of_the_text_being_edited(api):
    edited = TEXT.replace(
        "    note = models.TextField(blank=True)\n",
        "    note = models.TextField(blank=True)\n    gift = models.BooleanField(default=False)\n",
    )
    status, schema = api("POST", "/api/schema/preview", {"path": PATH, "content": edited})
    assert status == 200
    order = next(model for model in schema["models"] if model["name"] == "Order")
    assert "gift" in [field["name"] for field in order["fields"]]
    # Located in the text being edited, not in the file on disk.
    assert order["location"]["line"] == edited.splitlines().index("class Order(models.Model):") + 1
    # The file and the project Studio serves are as they were.
    assert (ROOT / PATH).read_text() == TEXT
    _status, snapshot = api("GET", "/api/schema")
    served = next(model for model in snapshot["schema"]["models"] if model["name"] == "Order")
    assert "gift" not in [field["name"] for field in served["fields"]]


def test_preview_of_a_text_that_does_not_load_says_why(api):
    broken = TEXT.replace("class Order(models.Model):", "class Order(models.Model)")
    status, body = api("POST", "/api/schema/preview", {"path": PATH, "content": broken})
    assert status == 422
    assert body["detail"].startswith("SyntaxError: expected ':'")
    refused = TEXT.replace("max_length=100", "max_lenght=100", 1)
    status, body = api("POST", "/api/schema/preview", {"path": PATH, "content": refused})
    assert status == 422
    assert "unexpected keyword argument 'max_lenght'" in body["detail"]
