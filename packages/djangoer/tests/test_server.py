import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from djangoer.cli import settings_from_manage_py
from djangoer.studio.server import create_server


@pytest.fixture
def server(tmp_path):
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>Studio</title>")
    (static / "assets" / "app.js").write_text("console.log(1)")
    instance = create_server("127.0.0.1", 0, root=Path(__file__).parent, static_dir=static)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    address = f"http://127.0.0.1:{instance.server_address[1]}"
    # The socket is bound already; the app answers once uvicorn has started on it.
    deadline = time.monotonic() + 10
    while not instance.server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    yield address
    instance.shutdown()
    thread.join(timeout=5)
    instance.server_close()


def fetch(url, *, method="GET", body=None, headers=None):
    request = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.headers, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read()


def test_serves_the_client_and_falls_back_to_the_entry_page(server):
    status, headers, body = fetch(server + "/")
    assert status == 200 and b"Studio" in body
    assert headers["Cache-Control"] == "no-cache"
    status, _headers, body = fetch(server + "/models/Customer")
    assert status == 200 and b"Studio" in body
    status, headers, body = fetch(server + "/assets/app.js")
    assert status == 200 and body == b"console.log(1)"
    assert "immutable" in headers["Cache-Control"]
    assert fetch(server + "/assets/missing.js")[0] == 404
    # Nothing outside the client's directory is served.
    status, _headers, body = fetch(server + "/../conftest.py")
    assert status == 404 and b"pytest" not in body


def test_api_over_http(server):
    status, headers, body = fetch(server + "/api/db")
    assert status == 200
    assert headers["Content-Type"] == "application/json"
    assert json.loads(body)["connected"] is True
    status, headers, body = fetch(server + "/api/db/rows/Nope")
    assert status == 404
    assert headers["Content-Type"] == "application/problem+json"
    assert fetch(server + "/api/nope")[0] == 404


def test_only_json_from_this_host_may_write(server):
    body = json.dumps({"sql": "select 1 as one"}).encode()
    status, _headers, raw = fetch(
        server + "/api/db/sql",
        method="POST",
        body=body,
        headers={"Content-Type": "application/json"},
    )
    assert status == 200 and json.loads(raw)["rows"] == [{"one": 1}]
    # What a form on another site can send.
    status, _headers, _raw = fetch(
        server + "/api/db/sql", method="POST", body=body, headers={"Content-Type": "text/plain"}
    )
    assert status == 415
    status, _headers, _raw = fetch(server + "/api/db", headers={"Host": "evil.example"})
    assert status == 403


def test_events_stream_starts_with_ready(server):
    request = urllib.request.Request(server + "/api/schema/events")
    with urllib.request.urlopen(request, timeout=5) as response:
        assert response.headers["Content-Type"].startswith("text/event-stream")
        # First, how soon a listener should connect again after the server restarts.
        assert response.readline() == b"retry: 1000\n"
        response.readline()
        assert response.readline() == b"event: ready\n"
        assert response.readline().startswith(b"data: ")
        response.readline()
        # A reload is announced to whoever is listening.
        fetch(server + "/api/schema/reload", method="POST")
        assert response.readline() == b"event: change\n"


def test_settings_module_is_read_from_manage_py(tmp_path):
    (tmp_path / "manage.py").write_text(
        'import os\n\ndef main():\n    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")\n'
    )
    assert settings_from_manage_py(tmp_path) == "mysite.settings"
    assert settings_from_manage_py(tmp_path / "nope") is None


def test_a_project_that_does_not_load_says_why_and_serves_nothing_else(tmp_path):
    from fastapi.testclient import TestClient

    from djangoer.studio.app import create_app
    from djangoer.studio.brands import Alias
    from djangoer.studio.state import State

    broken = tmp_path / "shop" / "models.py"
    broken.parent.mkdir()
    broken.write_text("class Customer(models.Model)\n    name = 1\n")
    with pytest.raises(SyntaxError) as raised:
        compile(broken.read_text(), str(broken), "exec")
    state = State(Alias("default"), tmp_path, raised.value)
    client = TestClient(create_app(state), base_url="http://127.0.0.1")

    snapshot = client.get("/api/schema").json()
    assert snapshot["schema"] is None
    assert snapshot["error"].startswith("SyntaxError: ")
    assert snapshot["diagnostics"][0]["path"] == "shop/models.py"
    assert snapshot["diagnostics"][0]["range"]["start"] == {"line": 0, "character": 0}
    # The file as it is, so the page can show the line while it is being fixed.
    assert snapshot["files"] == [{"path": "shop/models.py", "content": broken.read_text()}]
    response = client.get("/api/db")
    assert response.status_code == 503
    assert response.json()["detail"].startswith("The project does not load: SyntaxError")


def test_a_model_file_is_written_back_and_no_other_file(tmp_path):
    from fastapi.testclient import TestClient

    from djangoer.studio import contract
    from djangoer.studio.app import create_app
    from djangoer.studio.brands import Alias
    from djangoer.studio.state import State

    models = tmp_path / "shop" / "models.py"
    models.parent.mkdir()
    models.write_text("# before\n")
    (tmp_path / "secret.py").write_text("KEY = 1\n")
    state = State(Alias("default"), tmp_path)
    # The files Studio lists are the ones that may be written.
    state.snapshot = state.snapshot.model_copy(
        update={"files": [contract.SchemaFile(path="shop/models.py", content="# before\n")]}
    )
    client = TestClient(create_app(state), base_url="http://127.0.0.1")

    written = client.put(
        "/api/schema/files", json={"path": "shop/models.py", "content": "# after\n"}
    )
    assert written.status_code == 200
    assert written.json() == {"path": "shop/models.py", "content": "# after\n"}
    assert models.read_text() == "# after\n"

    for path in ("secret.py", "../outside.py", "shop/../secret.py", str(tmp_path / "secret.py")):
        refused = client.put("/api/schema/files", json={"path": path, "content": "x"})
        assert refused.status_code == 404, path
        assert "is not one of the project's model files" in refused.json()["detail"]
    assert (tmp_path / "secret.py").read_text() == "KEY = 1\n"
    assert not (tmp_path.parent / "outside.py").exists()

    # A file the system refuses to write is a problem on `path`, not a crash.
    models.unlink()
    models.mkdir()
    failed = client.put("/api/schema/files", json={"path": "shop/models.py", "content": "x"})
    assert failed.status_code == 422
    assert failed.json()["errors"][0]["field"] == "path"
