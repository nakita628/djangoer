"""Running a query: the value it gives and every SQL statement it sent on the way.

This is the project's own code path — the same ORM, the same database — so it is as powerful as
`manage.py shell`. The checks made first (no imports, no private names) keep a typo or a pasted
snippet from wandering off; they are rails, not a sandbox, and Studio listens on localhost.
"""

from __future__ import annotations

import ast
import time
from typing import Any

import django
from django.db import connections, models, transaction
from django.db.models.query import QuerySet, RawQuerySet
from returns.result import Failure, Result, Success

from ...errors import QueryError, StudioError
from ...inputs import Input, RunQuery
from .. import values
from ..attempt import attempt
from ..sqlformat import format_sql
from .analyze import inspect
from .infer import SAFE_BUILTINS, namespace

# Rows shown for a queryset that sets no limit of its own.
MAX_ROWS = 1000


class Recorder:
    """An `execute_wrapper` that keeps each statement with its parameters and its time."""

    def __init__(self) -> None:
        self.queries: list[dict[str, Any]] = []

    def __call__(self, execute, sql, params, many, context):
        started = time.perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            elapsed = (time.perf_counter() - started) * 1000
            if many:
                flat = [values.cell(value) for row in (params or []) for value in row]
            elif isinstance(params, dict):
                flat = [values.cell(value) for value in params.values()]
            else:
                flat = [values.cell(value) for value in (params or [])]
            self.queries.append(
                {
                    "sql": sql,
                    "formatted": format_sql(sql),
                    "params": flat,
                    "durationMs": round(elapsed, 3),
                }
            )


def _materialize(value: Any) -> tuple[Any, int | None, bool]:
    """A result as JSON, with its row count and whether rows were left out."""
    if isinstance(value, models.Manager):
        value = value.all()
    if isinstance(value, QuerySet):
        if value.query.is_sliced:
            rows = list(value)
            truncated = False
        else:
            rows = list(value[: MAX_ROWS + 1])
            truncated = len(rows) > MAX_ROWS
            rows = rows[:MAX_ROWS]
        return [values.to_json(row) for row in rows], len(rows), truncated
    if isinstance(value, RawQuerySet):
        rows = []
        truncated = False
        for row in value:
            if len(rows) == MAX_ROWS:
                truncated = True
                break
            rows.append(row)
        return [values.to_json(row) for row in rows], len(rows), truncated
    if isinstance(value, (list, tuple, set, frozenset)):
        items = list(value)
        truncated = len(items) > MAX_ROWS
        return [values.to_json(item) for item in items[:MAX_ROWS]], len(items), truncated
    if hasattr(value, "__next__"):
        # A generator or `.iterator()`: read as far as the limit.
        items = []
        truncated = False
        for item in value:
            if len(items) == MAX_ROWS:
                truncated = True
                break
            items.append(item)
        return [values.to_json(item) for item in items], len(items), truncated
    return values.to_json(value), None, False


def checked(query: str) -> Result[ast.Module, StudioError]:
    """The syntax tree of a query that may run: nothing the checks refuse, and something to run."""
    result = inspect(query)
    if result["errors"]:
        return Failure(QueryError(tuple(error["message"] for error in result["errors"])))
    tree = ast.parse(query)
    if not tree.body:
        return Failure(QueryError(("There is no query to run.",)))
    return Success(tree)


def _run(alias: str, tree: ast.Module, *, commit: bool) -> dict[str, Any]:
    scope = namespace()
    scope["__builtins__"] = dict(SAFE_BUILTINS)
    last = tree.body[-1]
    body = tree.body[:-1] if isinstance(last, ast.Expr) else tree.body
    recorder = Recorder()
    connection = connections[alias]
    started = time.perf_counter()
    result: Any = None
    count: int | None = None
    truncated = False
    # What the query raises leaves the block as an exception, so the transaction is rolled back.
    with transaction.atomic(using=alias), connection.execute_wrapper(recorder):
        if body:
            module = ast.Module(body=body, type_ignores=[])
            exec(compile(module, "<query>", "exec"), scope)  # noqa: S102 - see the module docstring
        if isinstance(last, ast.Expr):
            expression = ast.Expression(body=last.value)
            value = eval(compile(expression, "<query>", "eval"), scope)  # noqa: S307
            # Still inside the wrapper: a queryset sends its SQL when it is read.
            result, count, truncated = _materialize(value)
        if not commit:
            transaction.set_rollback(True, using=alias)
    return {
        "result": result,
        "rowCount": count,
        "truncated": truncated,
        "queries": recorder.queries,
        "durationMs": round((time.perf_counter() - started) * 1000, 3),
    }


def _raised(error: Exception) -> StudioError:
    """Whatever the query raised is the answer: `DoesNotExist: Author matching query does not exist.`"""
    return QueryError((f"{type(error).__name__}: {error}",))


def execute(alias: str, query: str, *, commit: bool) -> Result[dict[str, Any], StudioError]:
    """Run a query in one transaction: kept when `commit`, rolled back otherwise."""
    return checked(query).bind(
        lambda tree: attempt(lambda: _run(alias, tree, commit=commit), (Exception,), _raised)
    )


def status(input: Input):
    """The ORM the playground runs queries through. It takes nothing: it is always this one."""
    del input
    return {
        "available": True,
        "source": f"Django {django.get_version()}",
        "error": None,
        "typescript": None,
        "typesError": None,
    }


def run(input: RunQuery):
    return execute(input.alias, input.query, commit=True)


def preview(input: RunQuery):
    """The SQL a read sends, from running it in a transaction that is rolled back.

    Only a query that can do nothing but read is run here, since the preview follows the typing.
    A rollback undoes rows, not the email a `save()` sent or the API a method called: whatever
    writes, or calls the project's own methods, shows its SQL when it is run on purpose.
    """
    if not inspect(input.query)["pure"]:
        return checked(input.query).map(lambda _tree: {"queries": [], "durationMs": 0})
    return execute(input.alias, input.query, commit=False).map(
        lambda result: {"queries": result["queries"], "durationMs": result["durationMs"]}
    )
