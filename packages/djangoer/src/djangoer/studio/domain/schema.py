"""Django models as the schema Studio shows: models, fields, enums and relations.

The shape is the one Hekireki Studio serves for a Prisma schema, so the same client renders it. A
ForeignKey becomes two fields as it is two things in Django too: the scalar ``author_id`` (the
column, what a row carries) and the object ``author`` (the relation, what the ORM follows).
"""

from __future__ import annotations

import enum
import inspect
import sysconfig
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from django.apps import apps
from django.db import connections, models
from django.db.models.fields import NOT_PROVIDED
from django.db.models.fields.related import ForeignObjectRel


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
        db_default = getattr(field, "db_default", NOT_PROVIDED)
        return None if db_default is NOT_PROVIDED else f"db_default={_repr(db_default)}"
    if callable(field.default):
        return f"{_repr(field.default)}()"
    if isinstance(field.default, enum.Enum):
        return repr(field.default.value)
    return _repr(field.default)


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


def _enum_name(model: type[models.Model], field: models.Field) -> str:
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
    return f"{model.__name__}{''.join(part.title() for part in field.name.split('_'))}"


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
    if not doc or doc.startswith(f"{model.__name__}("):
        return None
    return doc


def _scalar_field(
    model: type[models.Model], field: models.Field, alias: str, enums: dict[str, dict]
) -> dict[str, Any]:
    kind = "scalar"
    type_name = type(field).__name__
    if field.choices:
        kind = "enum"
        type_name = _enum_name(model, field)
        enums.setdefault(
            type_name,
            {
                "name": type_name,
                "dbName": None,
                "documentation": None,
                "values": _enum_values(model, field),
                "location": None,
            },
        )
    documentation = str(field.help_text) if field.help_text else None
    return {
        "name": field.attname,
        "dbName": field.column if field.column != field.attname else None,
        "kind": kind,
        "type": type_name,
        "isList": False,
        "isRequired": not field.null,
        "isId": bool(field.primary_key),
        "isUnique": bool(field.unique and not field.primary_key),
        "isUpdatedAt": bool(getattr(field, "auto_now", False)),
        "isForeignKey": bool((field.is_relation and field.many_to_one) or field.one_to_one),
        "default": _default(field),
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


def _indexes(model: type[models.Model]) -> list[dict[str, Any]]:
    meta = model._meta
    out: list[dict[str, Any]] = []
    for group in meta.unique_together:
        fields = [meta.get_field(name).attname for name in group]
        out.append(
            {
                "type": "unique",
                "name": None,
                "dbName": None,
                "fields": fields,
                "attribute": f"unique_together = {tuple(group)!r}",
            }
        )
    for constraint in meta.constraints:
        if isinstance(constraint, models.UniqueConstraint) and constraint.fields:
            out.append(
                {
                    "type": "unique",
                    "name": constraint.name,
                    "dbName": constraint.name,
                    "fields": [meta.get_field(name).attname for name in constraint.fields],
                    "attribute": (
                        f"UniqueConstraint(fields={list(constraint.fields)!r}, "
                        f"name={constraint.name!r})"
                    ),
                }
            )
    for index in meta.indexes:
        fields = [name.lstrip("-") for name in index.fields]
        out.append(
            {
                "type": "normal",
                "name": index.name,
                "dbName": index.name,
                "fields": [meta.get_field(name).attname for name in fields],
                "attribute": f"Index(fields={list(index.fields)!r}, name={index.name!r})",
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
    for field in meta.get_fields():
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
        if not getattr(field, "concrete", False) or getattr(field, "column", None) is None:
            # GenericForeignKey, CompositePrimaryKey: nothing a row carries under that name.
            continue
        fields.append(_scalar_field(model, field, alias, enums))
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
    return {
        "name": known.of(model),
        "app": meta.app_label,
        "dbName": meta.db_table,
        "documentation": _documentation(model),
        "annotations": [],
        "fields": fields,
        "primaryKey": key if len(key) > 1 else None,
        "indexes": _indexes(model),
        "attributes": _meta_attributes(model),
        # Where the class is written, when it is the project's: the source page opens there.
        "location": _location(model, root) if _in_project(_source_file(model), root) else None,
    }


def build_relations(model_list: list[type[models.Model]], known: Names) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for model in model_list:
        child = known.of(model)
        for field in model._meta.get_fields():
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
                }
            )
    return out


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
    return {
        "files": _files(model_list, root),
        "provider": connections[alias].vendor if alias in connections else None,
        "models": built,
        "enums": list(enums.values()),
        "relations": build_relations(model_list, known),
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
