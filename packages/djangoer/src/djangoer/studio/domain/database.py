"""The database behind the models: status, row counts, rows, SQL and its plan."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import DatabaseError, connections, models, transaction
from django.db.models import ProtectedError, Q, RestrictedError
from returns.result import Failure, Result, Success

from ..errors import (
    DatabaseRejectedError,
    DatabaseUnavailableError,
    FieldProblem,
    InvalidInputError,
    StudioError,
    UnknownModelError,
)
from ..inputs import CreateRow, DeleteRow, OnDatabase, ReadRows, RunSql, UpdateRow
from . import values
from .attempt import attempt
from .schema import Names, names
from .sqlanalysis import to_format_placeholders

MAX_TAKE = 1000
DIALECTS = {"sqlite", "postgresql", "mysql"}


def dialect(alias: str) -> str | None:
    vendor = connections[alias].vendor
    return vendor if vendor in DIALECTS else None


def _url(alias: str) -> str:
    """Where the database is, with the password left out."""
    settings = connections[alias].settings_dict
    vendor = connections[alias].vendor
    name = str(settings.get("NAME") or "")
    if vendor == "sqlite":
        try:
            name = Path(name).resolve().relative_to(Path.cwd()).as_posix()
        except ValueError:
            pass
        return f"file:{name}"
    user = settings.get("USER") or ""
    auth = f"{user}:***@" if user and settings.get("PASSWORD") else (f"{user}@" if user else "")
    host = settings.get("HOST") or "localhost"
    port = f":{settings['PORT']}" if settings.get("PORT") else ""
    return f"{vendor}://{auth}{host}{port}/{name}"


def status(input: OnDatabase):
    alias = input.alias
    try:
        connections[alias].ensure_connection()
    except Exception as error:  # noqa: BLE001 - a database that cannot be reached is a status
        return {
            "connected": False,
            "dialect": None,
            "url": None,
            "source": "settings",
            "error": str(error),
        }
    return {
        "connected": True,
        "dialect": dialect(alias),
        "url": _url(alias),
        "source": "settings",
        "error": None,
    }


def counts(input: OnDatabase):
    alias = input.alias
    out: dict[str, int] = {}
    for name, model in names().items():
        try:
            out[name] = model._base_manager.using(alias).count()
        except DatabaseError:
            # A table that is not migrated yet has no rows to count.
            continue
    return {"counts": out}


def find_model(known: Names, name: str) -> Result[type[models.Model], StudioError]:
    model = known.get(name)
    return Success(model) if model is not None else Failure(UnknownModelError(name))


def _columns(model: type[models.Model]) -> list[models.Field]:
    return [field for field in model._meta.concrete_fields if field.column is not None]


def _key(model: type[models.Model]) -> list[str]:
    parts = getattr(model._meta.pk, "fields", None)
    return [field.attname for field in parts] if parts else [model._meta.pk.attname]


def _search(model: type[models.Model], text: str) -> Q:
    """Rows where any text column contains the search, or a number column equals it."""
    query = Q()
    for field in _columns(model):
        if field.is_relation:
            target = field.target_field
            lookup = field.attname
        else:
            target = field
            lookup = field.name
        if isinstance(
            target,
            (models.CharField, models.TextField, models.UUIDField, models.GenericIPAddressField),
        ):
            query |= Q(**{f"{lookup}__icontains": text})
        elif isinstance(target, (models.IntegerField, models.FloatField, models.DecimalField)):
            try:
                query |= Q(**{lookup: target.to_python(text)})
            except (ValidationError, ValueError, TypeError):
                continue
    return query


def _page(
    alias: str, model: type[models.Model], skip: int, take: int, search: str
) -> Result[dict[str, Any], StudioError]:
    columns = [field.attname for field in _columns(model)]
    key = _key(model)
    queryset = model._base_manager.using(alias).all()
    if search:
        queryset = queryset.filter(_search(model, search))

    def read() -> tuple[int, list[dict[str, Any]]]:
        return queryset.count(), list(queryset.order_by(*key).values(*columns)[skip : skip + take])

    return attempt(read, (DatabaseError,), lambda error: DatabaseUnavailableError(str(error))).map(
        lambda found: {
            "rows": [{column: values.cell(row[column]) for column in columns} for row in found[1]],
            "total": found[0],
            "skip": skip,
            "take": take,
            "key": key,
            "columns": columns,
        }
    )


def rows(input: ReadRows):
    search = (input.search or "").strip()
    return find_model(names(), input.model).bind(
        lambda model: _page(input.alias, model, input.skip, input.take, search)
    )


def convert(model: type[models.Model], row: dict[str, Any]) -> Result[dict[str, Any], StudioError]:
    """Cells keyed by column name, as the Python values their fields store."""
    by_attname = {field.attname: field for field in _columns(model)}
    out: dict[str, Any] = {}
    errors: list[FieldProblem] = []
    for column, raw in row.items():
        field = by_attname.get(column)
        if field is None:
            errors.append(FieldProblem(column, f'Unknown column "{column}".'))
            continue
        try:
            out[column] = values.from_cell(field, raw)
        except ValidationError as error:
            errors.append(FieldProblem(column, "; ".join(error.messages)))
        except (ValueError, TypeError) as error:
            errors.append(FieldProblem(column, str(error)))
    return Failure(InvalidInputError(tuple(errors))) if errors else Success(out)


def _rejected(error: Exception, field: str = "values") -> DatabaseRejectedError:
    """A write the database refused, as an error on the row."""
    return DatabaseRejectedError(field, str(error))


WRITE_EXCEPTIONS = (DatabaseError, ValidationError, ValueError, TypeError, FieldDoesNotExist)


def condition(
    model: type[models.Model], where: dict[str, Any]
) -> Result[dict[str, Any], StudioError]:
    """The row a write is about: a `where` that names nothing would be every row."""
    return convert(model, where).bind(
        lambda converted: (
            Success(converted)
            if converted
            else Failure(InvalidInputError.of("where", "where must name the row to change"))
        )
    )


def _save(
    alias: str, model: type[models.Model], converted: dict[str, Any]
) -> Result[int, StudioError]:
    def save() -> int:
        with transaction.atomic(using=alias):
            model(**converted).save(using=alias, force_insert=True)
        return 1

    return attempt(save, WRITE_EXCEPTIONS, _rejected)


def _update(
    alias: str, model: type[models.Model], where: dict[str, Any], converted: dict[str, Any]
) -> Result[int, StudioError]:
    def update_rows() -> int:
        with transaction.atomic(using=alias):
            return model._base_manager.using(alias).filter(**where).update(**converted)

    return attempt(update_rows, WRITE_EXCEPTIONS, _rejected)


def _delete(
    alias: str, model: type[models.Model], where: dict[str, Any]
) -> Result[int, StudioError]:
    def delete_rows() -> int:
        with transaction.atomic(using=alias):
            # Through the ORM, so on_delete is honoured: Django cascades in Python, not in the database.
            _total, per_model = model._base_manager.using(alias).filter(**where).delete()
        return per_model.get(model._meta.label, 0)

    def refused(error: Exception) -> StudioError:
        if isinstance(error, (ProtectedError, RestrictedError)):
            # The first argument is the sentence that names the rows in the way.
            return DatabaseRejectedError("where", str(error.args[0]))
        return _rejected(error)

    return attempt(delete_rows, (DatabaseError,), refused)


def insert(input: CreateRow):
    return Result.do(
        {"affected": affected}
        for model in find_model(names(), input.model)
        for converted in convert(model, input.values)
        for affected in _save(input.alias, model, converted)
    )


def update(input: UpdateRow):
    return Result.do(
        {"affected": affected}
        for model in find_model(names(), input.model)
        for row in condition(model, input.where)
        for converted in convert(model, input.values)
        # Nothing to set is nothing changed, not a statement the database would refuse.
        for affected in (_update(input.alias, model, row, converted) if converted else Success(0))
    )


def delete(input: DeleteRow):
    return Result.do(
        {"affected": affected}
        for model in find_model(names(), input.model)
        for row in condition(model, input.where)
        for affected in _delete(input.alias, model, row)
    )


def statement(sql: str) -> Result[str, StudioError]:
    """One statement as the cursor takes it: no trailing semicolon."""
    text = sql.strip().rstrip(";").strip()
    if not text:
        return Failure(InvalidInputError.of("sql", "sql must be a statement to run"))
    return Success(text)


def _sql_refused(error: Exception) -> StudioError:
    return DatabaseRejectedError("sql", str(error))


def _execute(alias: str, sql: str, params: list[Any]):
    """Run one statement as typed: with no parameters, a `%` in it is only a percent sign."""
    cursor = connections[alias].cursor()
    if params:
        cursor.execute(to_format_placeholders(sql), params)
    else:
        cursor.execute(sql)
    return cursor


def _unique(columns: list[str]) -> list[str]:
    """Column names of a result, a repeated one numbered so no value hides another."""
    seen: dict[str, int] = {}
    out = []
    for column in columns:
        count = seen.get(column, 0)
        seen[column] = count + 1
        out.append(column if count == 0 else f"{column}_{count + 1}")
    return out


def _run(alias: str, sql: str, params: list[Any]) -> dict[str, Any]:
    started = time.perf_counter()
    cursor = _execute(alias, sql, params)
    with cursor:
        if cursor.description:
            columns = _unique([column[0] for column in cursor.description])
            result = [
                {column: values.cell(value) for column, value in zip(columns, row)}
                for row in cursor.fetchall()
            ]
            count = len(result)
        else:
            columns, result = [], []
            count = max(cursor.rowcount, 0)
    return {
        "columns": columns,
        "rows": result,
        "rowCount": count,
        "durationMs": round((time.perf_counter() - started) * 1000, 3),
    }


def run_sql(input: RunSql):
    return statement(input.sql).bind(
        lambda text: attempt(
            lambda: _run(input.alias, text, input.params), (DatabaseError,), _sql_refused
        )
    )


def _plan_sqlite(cursor) -> tuple[list[dict[str, Any]], str]:
    nodes = []
    lines = []
    for node_id, parent, _unused, detail in cursor.fetchall():
        nodes.append(
            {
                "id": str(node_id),
                "parent": str(parent) if parent else None,
                "label": detail,
                "detail": None,
                "cost": None,
                "rows": None,
            }
        )
        lines.append(f"{node_id}|{parent}|{detail}")
    return nodes, "\n".join(lines)


def _plan_postgresql(cursor) -> tuple[list[dict[str, Any]], str]:
    raw = cursor.fetchone()[0]
    document = json.loads(raw) if isinstance(raw, str) else raw
    nodes: list[dict[str, Any]] = []

    def walk(plan: dict[str, Any], parent: str | None) -> None:
        node_id = str(len(nodes) + 1)
        label = plan.get("Node Type", "Plan")
        if plan.get("Relation Name"):
            label += f" on {plan['Relation Name']}"
        details = [
            f"{key}: {plan[key]}"
            for key in ("Index Name", "Index Cond", "Filter", "Hash Cond", "Join Type", "Sort Key")
            if plan.get(key)
        ]
        nodes.append(
            {
                "id": node_id,
                "parent": parent,
                "label": label,
                "detail": "; ".join(details) or None,
                "cost": plan.get("Total Cost"),
                "rows": plan.get("Plan Rows"),
            }
        )
        for child in plan.get("Plans", []):
            walk(child, node_id)

    for entry in document:
        walk(entry["Plan"], None)
    return nodes, json.dumps(document, indent=2)


def _plan_table(cursor) -> tuple[list[dict[str, Any]], str]:
    """MySQL's tabular EXPLAIN: one node per row, in the order the tables are read."""
    columns = [column[0] for column in cursor.description]
    nodes = []
    lines = []
    for index, row in enumerate(cursor.fetchall(), start=1):
        record = dict(zip(columns, row))
        label = " ".join(
            str(record[key]) for key in ("select_type", "table", "type") if record.get(key)
        )
        rows_value = record.get("rows")
        nodes.append(
            {
                "id": str(index),
                "parent": str(index - 1) if index > 1 else None,
                "label": label or f"step {index}",
                "detail": str(record.get("Extra")) if record.get("Extra") else None,
                "cost": None,
                "rows": float(rows_value) if rows_value is not None else None,
            }
        )
        lines.append(" | ".join(f"{key}={value}" for key, value in record.items()))
    return nodes, "\n".join(lines)


PLAN_PREFIX = {
    "sqlite": "EXPLAIN QUERY PLAN ",
    "postgresql": "EXPLAIN (FORMAT JSON) ",
    "mysql": "EXPLAIN ",
}


def _plan(alias: str, vendor: str, sql: str, params: list[Any]) -> dict[str, Any]:
    cursor = _execute(alias, PLAN_PREFIX[vendor] + sql, params)
    with cursor:
        if vendor == "sqlite":
            nodes, raw = _plan_sqlite(cursor)
        elif vendor == "postgresql":
            nodes, raw = _plan_postgresql(cursor)
        else:
            nodes, raw = _plan_table(cursor)
    return {"dialect": vendor, "nodes": nodes, "raw": raw}


def explain(input: RunSql):
    alias, sql, params = input.alias, input.sql, input.params
    vendor = dialect(alias)
    if vendor is None:
        return Failure(DatabaseUnavailableError(f"No plan for {connections[alias].vendor}."))
    return statement(sql).bind(
        lambda text: attempt(
            lambda: _plan(alias, vendor, text, params), (DatabaseError,), _sql_refused
        )
    )
