"""Each rule of lint/studio.py, on the smallest code that breaks it and the code that keeps it."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import studio


def rules(path: str, source: str) -> list[str]:
    return [finding.rule for finding in studio.check_file(path, source)]


def test_the_server_as_it_is_keeps_every_rule():
    assert studio.check() == []


def test_no_raise_and_no_except_in_the_layers_that_carry_values():
    raising = "def f():\n    raise ValueError('x')\n"
    catching = "def f():\n    try:\n        g()\n    except ValueError:\n        return None\n"
    for layer in ("handlers", "usecases", "services"):
        assert "no-raise" in rules(f"{layer}/x.py", raising)
        assert "no-except" in rules(f"{layer}/x.py", catching)
    # The domain is where an exception of Django becomes a value, so it may meet one.
    assert rules("domain/x.py", raising) == []
    assert rules("domain/x.py", catching) == []
    # try/finally catches nothing.
    assert (
        rules("services/x.py", "def _f():\n    try:\n        g()\n    finally:\n        h()\n")
        == []
    )


def test_no_unwrap_anywhere():
    assert rules("domain/x.py", "value = result.unwrap()\n") == ["no-unwrap"]
    assert rules("usecases/x.py", "def _f(r):\n    return r.failure()\n") == ["no-unwrap"]
    assert rules("domain/x.py", "value = result.map(str)\n") == []


def test_use_cases_and_services_leave_their_return_type_to_inference():
    annotated = (
        "def read(input: OnDatabase) -> Result[contract.Docs, StudioError]:\n    return f()\n"
    )
    assert rules("usecases/x.py", annotated) == ["inferred-return"]
    assert rules("services/x.py", annotated) == ["inferred-return"]
    assert rules("usecases/x.py", "def read(input: OnDatabase):\n    return f()\n") == []
    # A helper may say what its two branches are; a path operation names its response model.
    helper = "def _answering(found: DbStatus) -> Result[DbStatus, StudioError]:\n    return f()\n"
    assert rules("services/x.py", helper) == []
    assert "inferred-return" not in rules("handlers/x.py", annotated)


ROUTE = '@router.get("", operation_id="readDocs", response_model=contract.Docs)\n'
SUCCESS = "        case Success(value):\n            return value\n"


def handler(failure: str, subject: str = "DocsUseCase.read(state.alias)") -> str:
    return ROUTE + f"def read(request, state):\n    match {subject}:\n" + SUCCESS + failure


def test_a_path_operation_matches_every_error_of_its_use_case():
    nothing_to_fail = "        case Failure(error):\n            assert_never(error)\n"
    assert rules("handlers/x.py", handler(nothing_to_fail)) == []
    exhaustive = (
        "        case Failure(error):\n            match error:\n"
        "                case UnknownModelError():\n                    return problems.not_found(request, error)\n"
        "                case _:\n                    assert_never(error)\n"
    )
    assert rules("handlers/x.py", handler(exhaustive)) == []
    # A wildcard that answers instead of asserting would hide an error added later.
    swallowing = exhaustive.replace("assert_never(error)", "return problems.unexpected(request)")
    assert rules("handlers/x.py", handler(swallowing)) == ["handler-match"]
    no_wildcard = exhaustive.replace(
        "                case _:\n                    assert_never(error)\n", ""
    )
    assert rules("handlers/x.py", handler(no_wildcard)) == ["handler-match"]
    # The subject is a use case, called there: not a service, and not a value made earlier.
    assert rules("handlers/x.py", handler(nothing_to_fail, "DocsService.read()")) == [
        "handler-match"
    ]
    earlier = (
        ROUTE
        + "def read(state):\n    result = DocsUseCase.read()\n    match result:\n"
        + SUCCESS
        + nothing_to_fail
    )
    assert rules("handlers/x.py", earlier) == ["handler-match"]
    # A stream is not in the OpenAPI document and has no use case to match.
    stream = '@router.get("/events", include_in_schema=False)\nasync def events(state):\n    return StreamingResponse(go())\n'
    assert rules("handlers/x.py", stream) == []


def test_a_path_operation_names_its_contract():
    failure = "        case Failure(error):\n            assert_never(error)\n"
    body = "def read(state):\n    match DocsUseCase.read():\n" + SUCCESS + failure
    assert rules("handlers/x.py", '@router.get("")\n' + body) == [
        "route-contract",
        "route-contract",
    ]
    assert rules("handlers/x.py", '@router.get("", operation_id="readDocs")\n' + body) == [
        "route-contract"
    ]


def test_an_error_is_a_frozen_record():
    kept = "class StudioError:\n    pass\n\n@dataclass(frozen=True)\nclass NotFound(StudioError):\n    name: str\n"
    assert rules("errors.py", kept) == []
    assert rules("errors.py", "@dataclass\nclass NotFound(StudioError):\n    name: str\n") == [
        "error-record"
    ]
    exception = "@dataclass(frozen=True)\nclass NotFound(StudioError, Exception):\n    name: str\n"
    assert rules("errors.py", exception) == ["error-record"]


def test_a_use_case_and_a_service_take_one_input():
    result = ":\n    return Success(1)\n"
    assert rules("usecases/x.py", "def read(input: ReadRows)" + result) == []
    assert rules("usecases/x.py", "def read(alias: str, model: str)" + result) == ["single-input"]
    assert rules("services/x.py", "def read(body: ReadRows)" + result) == ["single-input"]
    assert rules("services/x.py", "def read(input: ReadRows, *, dry: bool)" + result) == [
        "single-input"
    ]
    assert rules("services/x.py", "def read(input: ReadRows, **more)" + result) == ["single-input"]
    # Helpers of a module, and the domain's own functions, are not held to it here.
    assert rules("services/x.py", "def _both(a: int, b: int) -> int:\n    return a + b\n") == []
    assert rules("domain/x.py", "def page(alias: str, skip: int) -> dict:\n    return {}\n") == []


def test_the_domain_takes_the_same_input_where_a_service_enters_it(tmp_path):
    (tmp_path / "services").mkdir()
    (tmp_path / "domain" / "orm").mkdir(parents=True)
    (tmp_path / "services" / "rows.py").write_text(
        "from ..domain import database\n"
        "from ..domain.docs import build_docs\n"
        "from ..domain.orm import run as orm_run\n\n"
        "def read(input):\n    return database.rows(input)\n\n"
        "def docs(input):\n    return build_docs(input)\n\n"
        "def run(input):\n    return orm_run.run(input)\n"
    )
    (tmp_path / "domain" / "database.py").write_text(
        "def rows(alias, model):\n    return _page(alias, 0)\n\n"
        "def _page(alias, skip):\n    return {}\n"
    )
    (tmp_path / "domain" / "docs.py").write_text("def build_docs(input):\n    return {}\n")
    (tmp_path / "domain" / "orm" / "run.py").write_text("def run(alias, query):\n    return 1\n")
    found = [(f.path, f.message.split("(")[0]) for f in studio.domain_single_input(tmp_path)]
    # rows() and run() are entered by a service; _page() and build_docs() are fine as they are.
    assert found == [("domain/database.py", "rows"), ("domain/orm/run.py", "run")]
