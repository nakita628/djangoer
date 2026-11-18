"""A server assumed when the database cannot be asked, so the docs need none.

Some of what Django writes depends on the server: its version on PostgreSQL (a
`UniqueConstraint` with `nulls_distinct` before Django 6.1), and on MySQL even the type of a
column (`connection.data_types` asks whether the server is a MariaDB with a native UUID), which
takes a connection. Where there is none, the connection is told a server for as long as it is
needed, and the docs say which.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, time
from decimal import Decimal
from functools import cached_property
from typing import Any

from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.utils.functional import cached_property as django_cached_property

# What a backend asks its server for, the value to assume when it cannot be asked, and how the
# docs name it: the newest server the supported Djangos know.
ASSUMED: dict[str, tuple[str, Any, str]] = {
    "postgresql": ("pg_version", 170000, "PostgreSQL 17"),
    "mysql": (
        "mysql_server_data",
        {
            "version": "8.4.0",
            "sql_mode": "",
            "default_storage_engine": "InnoDB",
            "sql_auto_is_null": False,
            "lower_case_table_names": 0,
            "has_zoneinfo_database": True,
        },
        "MySQL 8.4",
    ),
}
# The backends whose column types already depend on the server: asked once before anything is
# written, not when a statement fails.
TYPED_BY_SERVER = frozenset({"mysql"})


@contextmanager
def assumed(connection: Any) -> Iterator[str | None]:
    """The connection told a server (`ASSUMED`) for as long as the block runs, and the name of
    it; None for a backend with none to assume, or a server known already. Afterwards the
    server and what the backend worked out from it (its features, MySQL's `data_types`) are
    forgotten, so a connection that can reach its server later (Studio's) asks it."""
    entry = ASSUMED.get(connection.vendor)
    if entry is None or entry[0] in vars(connection):
        yield None
        return
    attribute, value, name = entry
    features = vars(connection.features)
    known_features = set(features)
    known = set(vars(connection))
    vars(connection)[attribute] = value
    try:
        yield name
    finally:
        for key in set(vars(connection)) - known:
            cached = getattr(type(connection), key, None)
            if key == attribute or isinstance(cached, (cached_property, django_cached_property)):
                vars(connection).pop(key, None)
        for key in set(features) - known_features:
            features.pop(key, None)


def unreachable(connection: Any) -> bool:
    """Whether the backend needs its server for the types of its columns and cannot ask it:
    tried once, with a connection that is closed again."""
    entry = ASSUMED.get(connection.vendor)
    if connection.vendor not in TYPED_BY_SERVER or entry is None or entry[0] in vars(connection):
        return False
    try:
        getattr(connection, entry[0])
    except Exception:  # noqa: BLE001 - whatever stops the connection, the server is assumed
        return True
    return False


@contextmanager
def offline(connection: Any) -> Iterator[str | None]:
    """A server assumed for the block when the column types need one and it cannot be asked
    (`unreachable`); the name of it, else None."""
    if not unreachable(connection):
        yield None
        return
    with assumed(connection) as name:
        yield name


def without_server(editor: Any) -> Any:
    """A schema editor that asks nothing of a server assumed (`assumed`): on MySQL, whether a
    foreign key gets an index of its own depends on the table's storage engine, which the
    editor asks the database with a cursor. The assumed server's default engine is taken."""
    connection = editor.connection
    entry = ASSUMED.get(connection.vendor)
    if (
        connection.vendor != "mysql"
        or entry is None
        or vars(connection).get(entry[0]) is not entry[1]
    ):
        return editor
    engine = entry[1]["default_storage_engine"]

    def should_be_indexed(model: Any, field: Any) -> bool:
        if not BaseDatabaseSchemaEditor._field_should_be_indexed(editor, model, field):
            return False
        # InnoDB indexes a foreign key's column for its constraint: Django adds none of its own.
        if engine == "InnoDB" and field.get_internal_type() == "ForeignKey" and field.db_constraint:
            return False
        return not editor._is_limited_data_type(field)

    editor._field_should_be_indexed = should_be_indexed
    editor.quote_value = _literal
    return editor


def _literal(value: Any) -> str:
    """A value as a MySQL literal, written without the driver: MySQL's editor has the
    connection escape it, which connects."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return f"X'{bytes(value).hex()}'"
    text = value.isoformat(sep=" ") if isinstance(value, datetime) else str(value)
    if isinstance(value, (date, time)) and not isinstance(value, datetime):
        text = value.isoformat()
    return "'" + text.replace("\\", "\\\\").replace("'", "''") + "'"
