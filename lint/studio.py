"""The conventions of the Studio server that neither ruff nor import-linter can express.

ruff holds every file to the language's rules and import-linter holds the layers to what they
may import (pyproject.toml). What is left is the shape of the code inside a layer, read here
from its syntax tree:

    no-raise              handlers, use cases and services raise nothing: an error is a value
    no-except             … and catch nothing: domain/attempt.py is where an exception becomes one
    no-unwrap             a Result is matched or mapped, never unwrapped
    inferred-return       a use case and a service leave their return type to inference, so the
                          errors a pipeline can fail with are the ones its steps have
    single-input          … and take one argument, `input`; so does the domain where a service
                          enters it
    handler-match         a path operation is one `match` on its use case: the value of a
                          Success, and for a Failure a `match` on the error that ends in
                          `assert_never(error)` — which is what makes a missing case an error
                          of the type checker
    route-contract        a path operation names its `operation_id` and its `response_model`
    error-record          an error is a frozen dataclass under StudioError, not an exception

Run it with `uv run python lint/studio.py` (`just lint` does).
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

STUDIO = Path(__file__).resolve().parent.parent / "packages/djangoer/src/djangoer/studio"
VALUE_LAYERS = ("handlers", "usecases", "services")
# The layers whose functions take one `input` (and, with the handlers, raise nothing).
RESULT_LAYERS = ("usecases", "services")
UNWRAPS = frozenset({"unwrap", "failure"})
# What the services are written with, not a service: it takes a contract and an effect to run,
# and raises only for a bug (a failure its service did not declare).
LAYER_TOOLS = frozenset({"services/effect.py"})
ROUTE_METHODS = frozenset({"get", "post", "put", "patch", "delete"})


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.rule}: {self.message}"


def layer_of(path: str) -> str | None:
    """`handlers/db.py` is in `handlers`; `errors.py` is in no layer."""
    parts = Path(path).parts
    return parts[0] if len(parts) > 1 else None


def _functions(tree: ast.Module) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _keyword(call: ast.Call, name: str) -> ast.expr | None:
    return next((keyword.value for keyword in call.keywords if keyword.arg == name), None)


def no_raise(path: str, tree: ast.Module) -> Iterator[Finding]:
    if layer_of(path) not in VALUE_LAYERS or path in LAYER_TOOLS:
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise):
            yield Finding(
                path,
                node.lineno,
                "no-raise",
                "return a Failure holding an error of errors.py instead of raising",
            )


def no_except(path: str, tree: ast.Module) -> Iterator[Finding]:
    if layer_of(path) not in VALUE_LAYERS:
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            yield Finding(
                path,
                node.lineno,
                "no-except",
                "an exception becomes a value in domain/attempt.py: take the Result it gives",
            )


def no_unwrap(path: str, tree: ast.Module) -> Iterator[Finding]:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in UNWRAPS
        ):
            yield Finding(
                path,
                node.lineno,
                "no-unwrap",
                f".{node.func.attr}() throws on the other case: match the Result, or map / bind it",
            )


def inferred_return(path: str, tree: ast.Module) -> Iterator[Finding]:
    """What a use case or a service returns is what its body says: a Result all the way up,
    which the type checker holds `respond` to. A helper may still say so (`_answering`), where
    two branches are one Result only because the annotation says they are. A path operation
    does annotate: its return type is its response model."""
    if layer_of(path) not in RESULT_LAYERS or path in LAYER_TOOLS:
        return
    for function in _functions(tree):
        if not function.name.startswith("_") and function.returns is not None:
            yield Finding(
                path,
                function.lineno,
                "inferred-return",
                f"{function.name}() must leave its return type to inference: drop `-> ...`",
            )


def takes_single_input(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """One positional parameter named `input`, and nothing else."""
    arguments = function.args
    return (
        [argument.arg for argument in arguments.args] == ["input"]
        and not arguments.posonlyargs
        and not arguments.kwonlyargs
        and arguments.vararg is None
        and arguments.kwarg is None
    )


def single_input(path: str, tree: ast.Module) -> Iterator[Finding]:
    if layer_of(path) not in RESULT_LAYERS or path in LAYER_TOOLS:
        return
    for function in _functions(tree):
        if not function.name.startswith("_") and not takes_single_input(function):
            yield Finding(
                path,
                function.lineno,
                "single-input",
                f"{function.name}() must take one argument, `input`: a record of inputs.py",
            )


def _domain_module(module: str | None, name: str, root: Path) -> tuple[str, str | None] | None:
    """What `from ..domain[.x] import name` names: (module path, function) under the domain.

    `name` is a module when there is a file for it (`from ..domain import database`), and
    otherwise a function of the module it is imported from (`from ..domain.docs import build_docs`).
    """
    if module is None or not (module == "domain" or module.startswith("domain.")):
        return None
    base = module.replace(".", "/")
    if (root / base / f"{name}.py").is_file():
        return f"{base}/{name}.py", None
    return f"{base}.py", name


def domain_entries(service: ast.Module, root: Path) -> Iterator[tuple[str, str, int]]:
    """The domain functions a service module calls: (module path, function, line of the call)."""
    modules: dict[str, str] = {}
    functions: dict[str, tuple[str, str]] = {}
    for node in service.body:
        if not (isinstance(node, ast.ImportFrom) and node.level == 2):
            continue
        for alias in node.names:
            target = _domain_module(node.module, alias.name, root)
            if target is None:
                continue
            local = alias.asname or alias.name
            if target[1] is None:
                modules[local] = target[0]
            else:
                functions[local] = (target[0], target[1])
    for node in ast.walk(service):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            module = modules.get(func.value.id)
            if module is not None:
                yield module, func.attr, node.lineno
        elif isinstance(func, ast.Name) and func.id in functions:
            yield (*functions[func.id], node.lineno)


def domain_single_input(root: Path) -> Iterator[Finding]:
    """A domain function a service calls takes the same one `input` the service was given."""
    seen: set[tuple[str, str]] = set()
    for file in sorted((root / "services").glob("*.py")):
        service = ast.parse(file.read_text(encoding="utf-8"))
        for module, name, _line in domain_entries(service, root):
            if (module, name) in seen or not (root / module).is_file():
                continue
            seen.add((module, name))
            tree = ast.parse((root / module).read_text(encoding="utf-8"))
            for function in _functions(tree):
                if function.name == name and not takes_single_input(function):
                    yield Finding(
                        module,
                        function.lineno,
                        "single-input",
                        f"{name}() is called by services/{file.name}: it must take one argument, `input`",
                    )


def _route(function: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.Call | None:
    """The `@router.get(...)` call that makes a function a path operation."""
    for decorator in function.decorator_list:
        if (
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr in ROUTE_METHODS
        ):
            return decorator
    return None


def _documented(route: ast.Call) -> bool:
    """A path operation is in the OpenAPI document unless it says `include_in_schema=False`."""
    value = _keyword(route, "include_in_schema")
    return not (isinstance(value, ast.Constant) and value.value is False)


def path_operations(
    tree: ast.Module,
) -> Iterator[tuple[ast.FunctionDef | ast.AsyncFunctionDef, ast.Call]]:
    for function in _functions(tree):
        route = _route(function)
        if route is not None and _documented(route):
            yield function, route


def _is_assert_never(statements: list[ast.stmt]) -> bool:
    """`assert_never(error)` and nothing else."""
    if len(statements) != 1 or not isinstance(statements[0], ast.Expr):
        return False
    call = statements[0].value
    return (
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "assert_never"
        and [ast.unparse(argument) for argument in call.args] == ["error"]
    )


def _class_pattern(case: ast.match_case, name: str, capture: str) -> bool:
    """`case Name(capture):`"""
    pattern = case.pattern
    return (
        isinstance(pattern, ast.MatchClass)
        and ast.unparse(pattern.cls) == name
        and len(pattern.patterns) == 1
        and isinstance(pattern.patterns[0], ast.MatchAs)
        and pattern.patterns[0].name == capture
        and case.guard is None
    )


def _is_wildcard(case: ast.match_case) -> bool:
    return (
        isinstance(case.pattern, ast.MatchAs)
        and case.pattern.pattern is None
        and case.pattern.name is None
    )


def _exhaustive_failure(body: list[ast.stmt]) -> bool:
    """What a path operation does with a Failure: nothing can reach it (`assert_never(error)`),
    or a `match error:` of class patterns whose last case is `case _: assert_never(error)`."""
    if _is_assert_never(body):
        return True
    if len(body) != 1 or not isinstance(body[0], ast.Match):
        return False
    inner = body[0]
    if ast.unparse(inner.subject) != "error" or len(inner.cases) < 2:
        return False
    *named, last = inner.cases
    return (
        all(isinstance(case.pattern, ast.MatchClass) and case.guard is None for case in named)
        and _is_wildcard(last)
        and _is_assert_never(last.body)
    )


def _matches_use_case(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    body = function.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]  # the docstring
    if len(body) != 1 or not isinstance(body[0], ast.Match):
        return False
    statement = body[0]
    subject = statement.subject
    if not (
        isinstance(subject, ast.Call)
        and isinstance(subject.func, ast.Attribute)
        and isinstance(subject.func.value, ast.Name)
        and subject.func.value.id.endswith("UseCase")
    ):
        return False
    if len(statement.cases) != 2:
        return False
    success, failure = statement.cases
    returns_value = (
        len(success.body) == 1
        and isinstance(success.body[0], ast.Return)
        and success.body[0].value is not None
        and ast.unparse(success.body[0].value) == "value"
    )
    return (
        _class_pattern(success, "Success", "value")
        and returns_value
        and _class_pattern(failure, "Failure", "error")
        and _exhaustive_failure(failure.body)
    )


def handler_match(path: str, tree: ast.Module) -> Iterator[Finding]:
    if layer_of(path) != "handlers":
        return
    for function, _route_call in path_operations(tree):
        if not _matches_use_case(function):
            yield Finding(
                path,
                function.lineno,
                "handler-match",
                f"{function.name}() must be one `match SomeUseCase.do(...)`: `case Success(value): return value`, "
                "then `case Failure(error):` with a `match error:` that ends in `case _: assert_never(error)`",
            )


def route_contract(path: str, tree: ast.Module) -> Iterator[Finding]:
    if layer_of(path) != "handlers":
        return
    for function, route in path_operations(tree):
        for keyword in ("operation_id", "response_model"):
            if _keyword(route, keyword) is None:
                yield Finding(
                    path,
                    route.lineno,
                    "route-contract",
                    f"the route of {function.name}() must name its {keyword}: the client is generated from it",
                )


def _is_frozen_dataclass(node: ast.ClassDef) -> bool:
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Call) and ast.unparse(decorator.func) == "dataclass":
            frozen = _keyword(decorator, "frozen")
            if isinstance(frozen, ast.Constant) and frozen.value is True:
                return True
    return False


def error_record(path: str, tree: ast.Module) -> Iterator[Finding]:
    if path != "errors.py":
        return
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = [ast.unparse(base) for base in node.bases]
        if any(base.endswith(("Exception", "Error")) and base != "StudioError" for base in bases):
            yield Finding(
                path,
                node.lineno,
                "error-record",
                f"{node.name} must not be an exception: an error is a value in a Failure",
            )
        if node.name != "StudioError" and not _is_frozen_dataclass(node):
            yield Finding(
                path,
                node.lineno,
                "error-record",
                f"{node.name} must be a `@dataclass(frozen=True)`",
            )


FILE_RULES = (
    no_raise,
    no_except,
    no_unwrap,
    inferred_return,
    single_input,
    handler_match,
    route_contract,
    error_record,
)


def check_file(path: str, source: str) -> list[Finding]:
    """Every finding of the per-file rules for one module, named relative to the Studio package."""
    tree = ast.parse(source)
    return [finding for rule in FILE_RULES for finding in rule(path, tree)]


def check(root: Path = STUDIO) -> list[Finding]:
    findings: list[Finding] = []
    for file in sorted(root.rglob("*.py")):
        relative = file.relative_to(root).as_posix()
        if relative.startswith("static/"):
            continue
        findings.extend(check_file(relative, file.read_text(encoding="utf-8")))
    findings.extend(domain_single_input(root))
    return findings


def main() -> int:
    findings = check()
    for finding in findings:
        print(finding)
    if findings:
        print(f"\n{len(findings)} finding{'s' if len(findings) != 1 else ''} in the Studio server.")
        return 1
    print("The Studio server keeps its conventions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
