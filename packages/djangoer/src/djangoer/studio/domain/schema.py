"""Django models as the schema Studio shows: models, fields, enums and relations.

The shape is the one Hekireki Studio serves for a Prisma schema, so the same client renders it. A
ForeignKey becomes two fields as it is two things in Django too: the scalar ``author_id`` (the
column, what a row carries) and the object ``author`` (the relation, what the ORM follows).
"""

from __future__ import annotations

import enum
import inspect
import re
import sysconfig
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db import connections, models
from django.db.models import F, Q
from django.db.models.fields import NOT_PROVIDED
from django.db.models.fields.related import ForeignObjectRel
from django.db.models.sql import Query


def _site_roots() -> list[Path]:
    roots = []
    for key in ("purelib", "platlib"):
        path = sysconfig.get_paths().get(key)
        if path:
            roots.append(Path(path).resolve())
    return roots


def display_path(file: str, root: Path) -> str:
    """A file as Studio names it: relative to the project, else to site-packages."""
    path = Path(file).resolve()
    for base in (root.resolve(), *_site_roots()):
        try:
            return path.relative_to(base).as_posix()
        except ValueError:
            continue
    return path.as_posix()


class Names:
    """The name each model goes by: its class name, or ``app_label.Name`` when two apps share it."""

    def __init__(self, model_list: list[type[models.Model]]):
        seen: dict[str, int] = {}
        for model in model_list:
            seen[model.__name__] = seen.get(model.__name__, 0) + 1
        self._by_model = {
            model: (
                model.__name__
                if seen[model.__name__] == 1
                else f"{model._meta.app_label}.{model.__name__}"
            )
            for model in model_list
        }
        self._by_name = {name: model for model, name in self._by_model.items()}

    def of(self, model: type[models.Model]) -> str | None:
        return self._by_model.get(model)

    def get(self, name: str) -> type[models.Model] | None:
        return self._by_name.get(name)

    def items(self):
        return self._by_name.items()


def studio_models() -> list[type[models.Model]]:
    """Every model with a table of its own: no proxies, no automatic many-to-many tables."""
    return [
        model
        for model in apps.get_models()
        if not model._meta.proxy and not model._meta.auto_created and not model._meta.swapped
    ]


def names() -> Names:
    return Names(studio_models())


def _repr(value: Any) -> str:
    if inspect.isclass(value) or inspect.isfunction(value) or inspect.isbuiltin(value):
        return getattr(value, "__qualname__", repr(value))
    if callable(value) and hasattr(value, "__qualname__"):
        return value.__qualname__
    return repr(value)


def _default(field: models.Field) -> str | None:
    if isinstance(field, (models.AutoField, models.BigAutoField, models.SmallAutoField)):
        return "autoincrement()"
    if getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False):
        return "now()"
    if field.default is NOT_PROVIDED:
        # A default of the database is `dbDefault`, as the SQL it is: not Python's.
        return None
    if callable(field.default):
        return f"{_repr(field.default)}()"
    if isinstance(field.default, enum.Enum):
        return repr(field.default.value)
    return _repr(field.default)


def _compiled(alias: str, build) -> str | None:
    """SQL Django writes for this database, its parameters in place; None when the backend
    cannot write it (or the Django is too old to have it)."""
    try:
        connection = connections[alias]
        editor = connection.schema_editor()
        sql, params = build(connection, editor)
    except Exception:  # noqa: BLE001 - a backend that cannot compile it offline
        return None
    return sql % tuple(editor.quote_value(param) for param in params) if params else sql


def _db_default(field: models.Field, alias: str) -> str | None:
    """`db_default` as the SQL the column is created with: `0`, `(CURRENT_TIMESTAMP)`."""
    if getattr(field, "db_default", NOT_PROVIDED) is NOT_PROVIDED:
        return None
    return _compiled(alias, lambda _connection, editor: editor.db_default_sql(field))


def _generated(field: models.Field, alias: str) -> str | None:
    """The expression of a `GeneratedField`, as the database computes it: `"price" + "tax"`."""
    if not getattr(field, "generated", False):
        return None
    return _compiled(alias, lambda connection, _editor: field.generated_sql(connection))


def _comments(*texts: object) -> str | None:
    """What describes a column or a table, each text once: the comment the database keeps
    (`db_comment`, `db_table_comment`) first, then the one of the code."""
    seen = [str(text).strip() for text in texts if text and str(text).strip()]
    return " — ".join(dict.fromkeys(seen)) or None


def _attributes(field: models.Field) -> list[str]:
    """The options the field was declared with, as they are written in models.py."""
    try:
        _name, _path, args, kwargs = field.deconstruct()
    except Exception:  # noqa: BLE001 - a third-party field may fail to deconstruct
        return []
    out = [_repr(arg) for arg in args]
    for key, value in kwargs.items():
        if key == "to":
            continue
        if key == "on_delete":
            out.append(f"on_delete={getattr(value, '__name__', _repr(value))}")
        elif key == "choices":
            out.append("choices=…")
        else:
            out.append(f"{key}={_repr(value)}")
    return out


def _native_type(field: models.Field, alias: str) -> str | None:
    try:
        return field.db_type(connections[alias])
    except Exception:  # noqa: BLE001 - no column type without a usable connection
        return None


def _enum_name(model: type[models.Model], field: models.Field, owner: str) -> str:
    """The Choices class a field's choices came from, else a name made from model and field."""
    choices = list(field.flatchoices)
    candidates: list[type] = []
    for holder in (model, inspect.getmodule(model)):
        if holder is None:
            continue
        for value in vars(holder).values():
            if inspect.isclass(value) and issubclass(value, models.Choices):
                candidates.append(value)
    for candidate in candidates:
        if list(candidate.choices) == choices:
            # `Post.Status` is PostStatus: many models have a Status of their own.
            return candidate.__qualname__.replace(".", "")
    return f"{owner}{''.join(part.title() for part in field.name.split('_'))}"


def _enum_values(model: type[models.Model], field: models.Field) -> list[dict[str, Any]]:
    labels: dict[Any, str] = {}
    for holder in (model, inspect.getmodule(model)):
        if holder is None:
            continue
        for value in vars(holder).values():
            if (
                inspect.isclass(value)
                and issubclass(value, models.Choices)
                and list(value.choices) == list(field.flatchoices)
            ):
                labels = {member.value: member.name for member in value}
    return [
        {"name": labels.get(value, str(label)), "dbName": str(value)}
        for value, label in field.flatchoices
    ]


def _location(obj: Any, root: Path) -> dict[str, Any] | None:
    try:
        file = inspect.getsourcefile(obj)
        _lines, line = inspect.getsourcelines(obj)
    except (OSError, TypeError):
        return None
    if file is None:
        return None
    return {"file": display_path(file, root), "line": line}


def _documentation(model: type[models.Model]) -> str | None:
    doc = inspect.cleandoc(model.__doc__ or "")
    # Django writes `Name(field, field, …)` as the docstring of a model that has none.
    if doc.startswith(f"{model.__name__}("):
        doc = ""
    return _comments(getattr(model._meta, "db_table_comment", None), doc)


def _camel(text: str) -> str:
    """`cas_server` → `CasServer`, `blog.Product` → `BlogProduct`."""
    return "".join(part[:1].upper() + part[1:] for part in re.split(r"[._]", text))


def _enum(
    model: type[models.Model], field: models.Field, owner: str, enums: dict[str, dict]
) -> str:
    """The name of a field's enum, registered in `enums` with its values.

    A model named by its app (`blog.Product`, as another app has a `Product`) names its enums
    by its app too: `BlogProductStatus`. Two enums that still meet under one name with other
    values (a `Product.Status` in two apps) are told apart by the app, then by a number: the
    second one's values are not to be lost to the first one's.
    """
    values = _enum_values(model, field)

    def taken(name: str) -> bool:
        return name in enums and enums[name]["values"] != values

    name = _enum_name(model, field, _camel(owner))
    if taken(name):
        name = _camel(model._meta.app_label) + name
    stem, number = name, 2
    while taken(name):
        name, number = f"{stem}{number}", number + 1
    enums.setdefault(
        name,
        {"name": name, "dbName": None, "documentation": None, "values": values, "location": None},
    )
    return name


def _scalar_field(
    model: type[models.Model],
    field: models.Field,
    alias: str,
    enums: dict[str, dict],
    owner: str | None = None,
) -> dict[str, Any]:
    """A column. `owner` is the name the model goes by (`blog.Product`), for its enums."""
    kind = "scalar"
    type_name = type(field).__name__
    if field.choices:
        kind = "enum"
        type_name = _enum(model, field, owner or model.__name__, enums)
    documentation = _comments(getattr(field, "db_comment", None), field.help_text)
    generated = _generated(field, alias)
    return {
        "name": field.attname,
        "dbName": field.column if field.column != field.attname else None,
        "kind": kind,
        "type": type_name,
        "isList": False,
        # A generated column is created without NOT NULL, whatever `null` says.
        "isRequired": not field.null and generated is None,
        "isId": bool(field.primary_key),
        "isUnique": bool(field.unique and not field.primary_key),
        "isUpdatedAt": bool(getattr(field, "auto_now", False)),
        "isForeignKey": bool((field.is_relation and field.many_to_one) or field.one_to_one),
        "default": _default(field),
        "dbDefault": _db_default(field, alias),
        "generated": generated,
        "nativeType": _native_type(field, alias),
        "documentation": documentation,
        "annotations": [],
        "relation": None,
        "attributes": _attributes(field),
    }


def _object_field(
    name: str,
    target: str,
    *,
    is_list: bool,
    required: bool,
    relation: dict[str, Any],
    attributes: list[str],
    documentation: str | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "dbName": None,
        "kind": "object",
        "type": target,
        "isList": is_list,
        "isRequired": required,
        "isId": False,
        "isUnique": False,
        "isUpdatedAt": False,
        "isForeignKey": False,
        "default": None,
        "dbDefault": None,
        "generated": None,
        "nativeType": None,
        "documentation": documentation,
        "annotations": [],
        "relation": relation,
        "attributes": attributes,
    }


def _relation_name(field: models.Field) -> str | None:
    """The name a relation was given: its `related_name`, when the model set one."""
    related_name = getattr(field.remote_field, "related_name", None)
    return related_name if related_name and not related_name.endswith("+") else None


def _sql(model: type[models.Model], alias: str, build) -> str | None:
    """A piece of SQL Django writes for a model on this database (an expression, a condition),
    with its parameters in place. None when the connection cannot write it."""
    try:
        connection = connections[alias]
        editor = connection.schema_editor()
        query = Query(model, alias_cols=False)
        sql, params = build(query, query.get_compiler(connection=connection), connection)
        return sql % tuple(editor.quote_value(param) for param in params)
    except Exception:  # noqa: BLE001 - a backend that cannot compile it offline
        return None


def _expressions(
    model: type[models.Model], expressions: tuple[Any, ...], alias: str
) -> tuple[list[str], list[str]]:
    """The fields and the expressions of an index declared with positional expressions.

    A bare field (`BrinIndex("last_seen")`) is a column like any other; anything else
    (`Lower("email")`) is written as the SQL it compiles to, or as Django writes it.
    """
    fields: list[str] = []
    out: list[str] = []
    for expression in expressions:
        if isinstance(expression, F):
            try:
                fields.append(model._meta.get_field(expression.name).attname)
                continue
            except FieldDoesNotExist:
                pass
        sql = _sql(
            model,
            alias,
            lambda query, compiler, _connection, e=expression: compiler.compile(
                e.resolve_expression(query)
            ),
        )
        out.append(sql or str(expression))
    return fields, out


def _condition(model: type[models.Model], condition: Q | None, alias: str) -> str | None:
    """The `WHERE` of a partial index, as SQL."""
    if condition is None:
        return None
    sql = _sql(
        model,
        alias,
        lambda query, compiler, connection: query.build_where(condition).as_sql(
            compiler, connection
        ),
    )
    return sql or str(condition)


def _editor(alias: str):
    """A schema editor of the database, to ask what it would create. It is never entered, so it
    runs nothing and needs no connection open."""
    try:
        return connections[alias].schema_editor()
    except Exception:  # noqa: BLE001 - no editor without a usable backend
        return None


def _unquoted(name: str, alias: str) -> str:
    quote = connections[alias].ops.quote_name("x")[0]
    return name[1:-1] if len(name) > 1 and name[0] == quote and name[-1] == quote else name


def _field_indexes(model: type[models.Model], alias: str) -> list[dict[str, Any]]:
    """The indexes the database creates for single columns, as its schema editor says: one for
    `db_index=True` and for every foreign key unless it says `db_index=False` (a unique column
    has its unique index already), and on PostgreSQL the `_like` index of a text column that is
    indexed or unique."""
    editor = _editor(alias)
    if editor is None:
        return []
    out: list[dict[str, Any]] = []
    for field in model._meta.local_concrete_fields:
        try:
            statements = editor._field_indexes_sql(model, field)
        except Exception:  # noqa: BLE001, S112 - a field the backend cannot index offline
            continue
        for statement in statements:
            name = _unquoted(str(statement.parts["name"]), alias)
            opclasses = list(getattr(statement.parts.get("columns"), "opclasses", None) or [])
            declared = type(field).__name__ if field.is_relation else "db_index=True"
            if opclasses:
                declared = f"{', '.join(opclasses)} for LIKE"
            out.append(
                {
                    "type": "normal",
                    "name": name,
                    "dbName": name,
                    "fields": [field.attname],
                    "expressions": [],
                    "condition": None,
                    "opclasses": opclasses,
                    "attribute": f"{field.name}: {declared}",
                }
            )
    return out


def _unique_together_name(model: type[models.Model], columns: list[str], alias: str):
    """The name Django gives the index of a `unique_together`: `orders_a_b_c7cdc6f9_uniq`."""
    editor = _editor(alias)
    if editor is None:
        return None
    try:
        return editor._create_index_name(model._meta.db_table, columns, suffix="_uniq")
    except Exception:  # noqa: BLE001 - no name without a usable backend
        return None


def _indexes(model: type[models.Model], alias: str) -> list[dict[str, Any]]:
    meta = model._meta
    out = _field_indexes(model, alias)
    for group in meta.unique_together:
        fields = [meta.get_field(name).attname for name in group]
        name = _unique_together_name(model, [meta.get_field(name).column for name in group], alias)
        out.append(
            {
                "type": "unique",
                "name": name,
                "dbName": name,
                "fields": fields,
                "expressions": [],
                "condition": None,
                "opclasses": [],
                "attribute": f"unique_together = {tuple(group)!r}",
            }
        )
    for constraint in meta.constraints:
        if not isinstance(constraint, models.UniqueConstraint):
            continue
        fields, expressions = _expressions(model, constraint.expressions, alias)
        fields += [meta.get_field(name).attname for name in constraint.fields]
        condition = _condition(model, constraint.condition, alias)
        declared = [*map(str, constraint.expressions)]
        if constraint.fields:
            declared.append(f"fields={list(constraint.fields)!r}")
        if constraint.condition is not None:
            declared.append(f"condition={constraint.condition!r}")
        if constraint.opclasses:
            declared.append(f"opclasses={list(constraint.opclasses)!r}")
        declared.append(f"name={constraint.name!r}")
        out.append(
            {
                "type": "unique",
                "name": constraint.name,
                "dbName": constraint.name,
                "fields": fields,
                "expressions": expressions,
                "condition": condition,
                "opclasses": list(constraint.opclasses),
                "attribute": f"UniqueConstraint({', '.join(declared)})",
            }
        )
    for index in meta.indexes:
        fields, expressions = _expressions(model, index.expressions, alias)
        fields += [meta.get_field(name.lstrip("-")).attname for name in index.fields]
        declared = [*map(str, index.expressions)]
        if index.fields:
            declared.append(f"fields={list(index.fields)!r}")
        if index.condition is not None:
            declared.append(f"condition={index.condition!r}")
        if index.opclasses:
            declared.append(f"opclasses={list(index.opclasses)!r}")
        declared.append(f"name={index.name!r}")
        out.append(
            {
                "type": "normal",
                "name": index.name,
                "dbName": index.name,
                "fields": fields,
                "expressions": expressions,
                "condition": _condition(model, index.condition, alias),
                "opclasses": list(index.opclasses),
                "attribute": f"{type(index).__name__}({', '.join(declared)})",
            }
        )
    return out


def _meta_attributes(model: type[models.Model]) -> list[str]:
    meta = model._meta
    out: list[str] = []
    default_table = f"{meta.app_label}_{meta.model_name}"
    if meta.db_table != default_table:
        out.append(f"db_table = {meta.db_table!r}")
    if meta.ordering:
        out.append(f"ordering = {list(meta.ordering)!r}")
    if not meta.managed:
        out.append("managed = False")
    return out


def _primary_key(model: type[models.Model]) -> list[str]:
    pk = model._meta.pk
    # Django 5.2's CompositePrimaryKey names the columns it is made of.
    parts = getattr(pk, "fields", None)
    if parts:
        return [field.attname for field in parts]
    return [pk.attname]


def build_model(
    model: type[models.Model], known: Names, alias: str, root: Path, enums: dict[str, dict]
) -> dict[str, Any]:
    meta = model._meta
    fields: list[dict[str, Any]] = []
    # The model's own fields: with multi-table inheritance the parent's are in the parent's
    # table, and the child has the link to it (`place_ptr_id`) and its own columns.
    for field in meta.get_fields(include_parents=False):
        if isinstance(field, ForeignObjectRel):
            # The other side of a relation declared elsewhere: `author.post_set`.
            accessor = field.get_accessor_name()
            target = known.of(field.related_model)
            if accessor is None or target is None:
                continue
            fields.append(
                _object_field(
                    accessor,
                    target,
                    is_list=bool(field.multiple),
                    required=False,
                    relation={
                        "declared": False,
                        "name": _relation_name(field.remote_field),
                        "fromFields": [],
                        "toFields": [],
                        "onDelete": None,
                        "onUpdate": None,
                    },
                    attributes=[],
                )
            )
            continue
        if field.many_to_many:
            target = known.of(field.related_model)
            if target is None:
                continue
            fields.append(
                _object_field(
                    field.name,
                    target,
                    is_list=True,
                    required=False,
                    relation={
                        "declared": True,
                        "name": _relation_name(field),
                        "fromFields": [],
                        "toFields": [],
                        "onDelete": None,
                        "onUpdate": None,
                    },
                    attributes=_attributes(field),
                    documentation=str(field.help_text) if field.help_text else None,
                )
            )
            continue
        composite = _composite_relation(field, known)
        if composite is not None:
            fields.append(composite)
            continue
        if not getattr(field, "concrete", False) or getattr(field, "column", None) is None:
            # GenericForeignKey, CompositePrimaryKey: nothing a row carries under that name.
            continue
        fields.append(_scalar_field(model, field, alias, enums, known.of(model)))
        if field.is_relation and (field.many_to_one or field.one_to_one):
            target = known.of(field.related_model)
            if target is None:
                continue
            on_delete = getattr(field.remote_field, "on_delete", None)
            fields.append(
                _object_field(
                    field.name,
                    target,
                    is_list=False,
                    required=not field.null,
                    relation={
                        "declared": True,
                        "name": _relation_name(field),
                        "fromFields": [field.attname],
                        "toFields": [field.target_field.attname],
                        "onDelete": getattr(on_delete, "__name__", None),
                        "onUpdate": None,
                    },
                    attributes=[],
                )
            )
    # What the model declares first, the accessors other models gave it last.
    fields.sort(key=lambda field: field["kind"] == "object" and not field["relation"]["declared"])
    for field in fields:
        if field["relation"] is not None:
            del field["relation"]["declared"]
    key = _primary_key(model)
    own = _in_project(_source_file(model), root)
    return {
        "name": known.of(model),
        "app": meta.app_label,
        "dbName": meta.db_table,
        "documentation": _documentation(model),
        "annotations": [],
        "fields": fields,
        "primaryKey": key if len(key) > 1 else None,
        "indexes": _indexes(model, alias),
        "genericForeignKeys": _generic_foreign_keys(model),
        "attributes": _meta_attributes(model),
        # Where the class is written, when it is the project's: the source page opens there.
        "location": _location(model, root) if own else None,
        # The project's own, by the module it is in: a model a package makes for one of the
        # project's (django-simple-history's `HistoricalArticle`) has no `class` statement to
        # be found at, but it is in the project's app, its database and its migrations.
        "own": own,
    }


def build_relations(
    model_list: list[type[models.Model]], known: Names, alias: str, enums: dict[str, dict]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for model in model_list:
        child = known.of(model)
        # A relation inherited from a concrete parent is the parent's, drawn once from it.
        for field in model._meta.get_fields(include_parents=False):
            if isinstance(field, ForeignObjectRel):
                continue
            if field.many_to_many:
                other = known.of(field.related_model)
                through = field.remote_field.through
                # A through model of its own is on the diagram already, with its two foreign keys.
                if other is None or not through._meta.auto_created:
                    continue
                inverse = field.remote_field.get_accessor_name() or field.name
                out.append(
                    {
                        "id": f"{child}.{field.name}<->{other}.{inverse}",
                        "name": _relation_name(field),
                        "origin": "implicit-many-to-many",
                        "from": {"model": child, "field": field.name, "cardinality": "zero-many"},
                        "to": {"model": other, "field": inverse, "cardinality": "zero-many"},
                        "onDelete": None,
                        "onUpdate": None,
                        "through": _through(field, alias, enums),
                    }
                )
                continue
            generic = _generic_relation(field, model, known)
            if generic is not None:
                out.append(generic)
                continue
            if _composite(field):
                parent = known.of(field.related_model)
                if parent is not None:
                    on_delete = getattr(field.remote_field, "on_delete", None)
                    target = field.related_model._meta.pk.name
                    # Each end names the field that stands for its columns: the composite key
                    # (`pk`), and the ForeignObject (`line`), which says which columns it reads.
                    out.append(
                        {
                            "id": f"{parent}.{target}->{child}.{field.name}",
                            "name": _relation_name(field),
                            "origin": "inferred",
                            "from": {
                                "model": parent,
                                "field": target,
                                "cardinality": "zero-one" if field.null else "one",
                            },
                            "to": {"model": child, "field": field.name, "cardinality": "zero-many"},
                            "onDelete": getattr(on_delete, "__name__", None),
                            "onUpdate": None,
                            "through": None,
                        }
                    )
                continue
            if not (field.is_relation and (field.many_to_one or field.one_to_one)):
                continue
            if getattr(field, "column", None) is None:
                continue
            parent = known.of(field.related_model)
            if parent is None:
                continue
            on_delete = getattr(field.remote_field, "on_delete", None)
            target = field.target_field.attname
            out.append(
                {
                    "id": f"{parent}.{target}->{child}.{field.attname}",
                    "name": _relation_name(field),
                    "origin": "inferred",
                    "from": {
                        "model": parent,
                        "field": target,
                        "cardinality": "zero-one" if field.null else "one",
                    },
                    "to": {
                        "model": child,
                        "field": field.attname,
                        "cardinality": "zero-one" if field.one_to_one else "zero-many",
                    },
                    "onDelete": getattr(on_delete, "__name__", None),
                    "onUpdate": None,
                    "through": None,
                }
            )
    return out


def _composite(field: Any) -> bool:
    """A `ForeignObject` of several columns, the way to refer to a composite primary key: a
    relation with no column of its own, its columns are other fields of the model."""
    return (
        isinstance(field, models.ForeignObject)
        and getattr(field, "column", None) is None
        and field.many_to_one
        and len(field.local_related_fields) > 0
    )


def _composite_relation(field: Any, known: Names) -> dict[str, Any] | None:
    """The object field of a `ForeignObject`: what it reads (`order_id`, `item_id`) and what
    that is on the other model."""
    if not _composite(field):
        return None
    target = known.of(field.related_model)
    if target is None:
        return None
    on_delete = getattr(field.remote_field, "on_delete", None)
    return _object_field(
        field.name,
        target,
        is_list=False,
        required=not field.null,
        relation={
            "declared": True,
            "name": _relation_name(field),
            "fromFields": [column.attname for column in field.local_related_fields],
            "toFields": [column.attname for column in field.foreign_related_fields],
            "onDelete": getattr(on_delete, "__name__", None),
            "onUpdate": None,
        },
        attributes=_attributes(field),
    )


def _generic_foreign_keys(model: type[models.Model]) -> list[dict[str, str]]:
    """The `GenericForeignKey`s of a model: a pair of columns that names a row of any model,
    the one of its content type and the one of its key."""
    out = []
    for field in model._meta.private_fields:
        # Told by its attributes: contenttypes is not imported unless the project installs it.
        ct_field, fk_field = getattr(field, "ct_field", None), getattr(field, "fk_field", None)
        if not (isinstance(ct_field, str) and isinstance(fk_field, str)):
            continue
        try:
            content_type = model._meta.get_field(ct_field).attname
            object_id = model._meta.get_field(fk_field).attname
        except FieldDoesNotExist:
            continue
        out.append(
            {"name": field.name, "contentTypeField": content_type, "objectIdField": object_id}
        )
    return out


def _generic_relation(field: Any, model: type[models.Model], known: Names) -> dict[str, Any] | None:
    """A `GenericRelation` as the relation it stands for: the rows of another model whose pair
    of columns names this model (`Rating.object_id`, where `content_type` is Article). Nothing
    in the database backs it, so it is a relation of its own kind, `generic`."""
    object_id = getattr(field, "object_id_field_name", None)
    if not (isinstance(object_id, str) and getattr(field, "content_type_field_name", None)):
        return None
    parent, child = known.of(model), known.of(field.related_model)
    if parent is None or child is None:
        return None
    try:
        column = field.related_model._meta.get_field(object_id).attname
    except FieldDoesNotExist:
        return None
    key = model._meta.pk.attname
    return {
        "id": f"{parent}.{key}~>{child}.{column}",
        "name": field.name,
        "origin": "generic",
        "from": {"model": parent, "field": key, "cardinality": "one"},
        "to": {"model": child, "field": column, "cardinality": "zero-many"},
        "onDelete": None,
        "onUpdate": None,
        "through": None,
    }


def _through(field: models.ManyToManyField, alias: str, enums: dict[str, dict]) -> dict[str, Any]:
    """The table Django creates for a many-to-many: its columns, which side each of the two
    keys refers to, and the indexes it has (one per key, and the pair unique).

    The columns are the through model's own, not only the key and the two sides: a field may
    give it more (django-sortedm2m's `sort_value`).
    """
    through = field.remote_field.through
    meta = through._meta
    source = meta.get_field(field.m2m_field_name())
    target = meta.get_field(field.m2m_reverse_field_name())
    return {
        "dbName": meta.db_table,
        "fromColumn": source.column,
        "toColumn": target.column,
        "fields": [
            _scalar_field(through, column, alias, enums) for column in meta.local_concrete_fields
        ],
        "indexes": _indexes(through, alias),
    }


def _in_project(file: str | None, root: Path) -> bool:
    """Whether a file is the project's own: under its directory and not an installed package."""
    if file is None:
        return False
    resolved = Path(file).resolve()
    return root.resolve() in resolved.parents and not any(
        base in resolved.parents for base in _site_roots()
    )


def _source_file(model: type[models.Model]) -> str | None:
    try:
        return inspect.getsourcefile(model)
    except TypeError:
        return None


def _files(model_list: list[type[models.Model]], root: Path) -> list[dict[str, str]]:
    """The source of the project's own models: its models.py, one per app.

    The models of installed packages (django.contrib.auth and the like) are in the schema and on
    the diagram, but their source is not the project's to read or change, so it is not listed.
    """
    seen: dict[str, str] = {}
    for model in model_list:
        file = _source_file(model)
        if file is None or file in seen or not _in_project(file, root):
            continue
        try:
            seen[file] = Path(file).read_text(encoding="utf-8")
        except OSError:
            continue
    ordered = sorted(seen, key=lambda file: display_path(file, root))
    return [{"path": display_path(file, root), "content": seen[file]} for file in ordered]


def build_schema(alias: str = "default", root: Path | None = None) -> dict[str, Any]:
    root = root or Path.cwd()
    # The project's own models first, then the ones of the packages it installs.
    model_list = sorted(
        studio_models(), key=lambda model: not _in_project(_source_file(model), root)
    )
    known = Names(model_list)
    enums: dict[str, dict] = {}
    built = [build_model(model, known, alias, root, enums) for model in model_list]
    # Before the enums are listed: a column of a many-to-many's table may have choices too.
    relations = build_relations(model_list, known, alias, enums)
    return {
        "files": _files(model_list, root),
        "provider": connections[alias].vendor if alias in connections else None,
        "models": built,
        "enums": list(enums.values()),
        "relations": relations,
    }


def build_snapshot(alias: str = "default", root: Path | None = None) -> dict[str, Any]:
    """The schema, or the reason there is none, with the time it was read."""
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    try:
        schema = build_schema(alias, root)
    except Exception as error:  # noqa: BLE001 - whatever broke, the page says so
        return {
            "schema": None,
            "error": str(error),
            "diagnostics": [],
            "updatedAt": now,
            "files": [],
        }
    return {
        "schema": schema,
        "error": None,
        "diagnostics": [],
        "updatedAt": now,
        "files": schema["files"],
    }


def _failure_location(error: BaseException, root: Path) -> tuple[str, int] | None:
    """Where a project failed to load: the line of a syntax error, else the innermost frame of
    the traceback that is the project's own code."""
    if isinstance(error, SyntaxError) and error.filename and error.lineno:
        return error.filename, error.lineno
    found: tuple[str, int] | None = None
    for frame in traceback.extract_tb(error.__traceback__):
        if frame.lineno is not None and _in_project(frame.filename, root):
            found = (frame.filename, frame.lineno)
    return found


def broken_snapshot(error: BaseException, root: Path) -> dict[str, Any]:
    """The snapshot of a project that does not load: why, where, and the file as it is, so the
    page can show the line while it is being fixed."""
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    message = f"{type(error).__name__}: {error}"
    location = _failure_location(error, root)
    diagnostics: list[dict[str, Any]] = []
    files: list[dict[str, str]] = []
    if location is not None:
        file, line = location
        path = display_path(file, root)
        diagnostics.append(
            {
                "path": path,
                "range": {
                    "start": {"line": line - 1, "character": 0},
                    "end": {"line": line, "character": 0},
                },
                "message": message,
                "severity": "error",
            }
        )
        try:
            files.append({"path": path, "content": Path(file).read_text(encoding="utf-8")})
        except OSError:
            pass
    return {
        "schema": None,
        "error": message,
        "diagnostics": diagnostics,
        "updatedAt": now,
        "files": files,
    }
