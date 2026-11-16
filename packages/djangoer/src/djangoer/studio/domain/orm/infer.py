"""What an ORM expression is, read from its syntax tree without running it.

`Post.objects.filter(...)` is a queryset of Post; `.first()` on it an instance; `.author` on that
an instance of Author. Everything the playground says before a query is run — which models it
touches, whether it writes, what can be typed next — is worked out here with `ast`.
"""

from __future__ import annotations

import ast
import builtins
import datetime
import decimal
import json
import uuid
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.db.models import functions
from django.db.models.fields.related import ForeignObjectRel
from django.utils import timezone

from ..schema import studio_models

# Methods of a manager or a queryset, by what they give back.
QUERYSET_METHODS = (
    "all",
    "filter",
    "exclude",
    "annotate",
    "alias",
    "order_by",
    "reverse",
    "distinct",
    "values",
    "values_list",
    "select_related",
    "prefetch_related",
    "only",
    "defer",
    "using",
    "none",
    "union",
    "intersection",
    "difference",
    "dates",
    "datetimes",
    "select_for_update",
    "extra",
    "raw",
)
INSTANCE_METHODS = ("get", "first", "last", "earliest", "latest", "create")
VALUE_METHODS = (
    "count",
    "exists",
    "aggregate",
    "update",
    "delete",
    "get_or_create",
    "update_or_create",
    "bulk_create",
    "bulk_update",
    "in_bulk",
    "iterator",
    "explain",
    "contains",
)
WRITE_METHODS = frozenset(
    {
        "create",
        "update",
        "delete",
        "get_or_create",
        "update_or_create",
        "bulk_create",
        "bulk_update",
        "save",
        "add",
        "remove",
        "clear",
        "set",
    }
)
# Methods whose keyword arguments are field lookups (`author__name__icontains=`).
LOOKUP_METHODS = frozenset({"filter", "exclude", "get", "get_or_create", "update_or_create"})
# Methods whose keyword arguments are the model's own fields.
FIELD_METHODS = frozenset({"create", "update"})
# Methods whose string arguments are field paths.
PATH_METHODS = frozenset(
    {
        "order_by",
        "values",
        "values_list",
        "only",
        "defer",
        "select_related",
        "prefetch_related",
        "distinct",
        "earliest",
        "latest",
        "dates",
        "datetimes",
    }
)
# After these a name may be one the query made up, so an unknown one is not a mistake.
ALIASING_METHODS = frozenset({"annotate", "alias", "extra", "values", "values_list", "raw"})
INSTANCE_WRITES = frozenset({"save", "delete"})

FORBIDDEN_NODES: tuple[tuple[type[ast.AST], str], ...] = (
    (
        ast.Import,
        "import is not available here: models, Q, F and the functions are already in scope",
    ),
    (
        ast.ImportFrom,
        "import is not available here: models, Q, F and the functions are already in scope",
    ),
    (ast.FunctionDef, "def is not available here"),
    (ast.AsyncFunctionDef, "async def is not available here"),
    (ast.ClassDef, "class is not available here"),
    (ast.While, "while is not available here: loop over a queryset with for"),
    (ast.With, "with is not available here: a query runs in a transaction already"),
    (ast.AsyncWith, "async with is not available here"),
    (ast.AsyncFor, "async for is not available here"),
    (ast.Await, "await is not available here: use the synchronous methods"),
    (ast.Try, "try is not available here"),
    (ast.Global, "global is not available here"),
    (ast.Nonlocal, "nonlocal is not available here"),
    (ast.Delete, "del is not available here: delete rows with .delete()"),
    (ast.Yield, "yield is not available here"),
    (ast.YieldFrom, "yield is not available here"),
)

SAFE_BUILTINS = {
    name: getattr(builtins, name)
    for name in (
        "abs",
        "all",
        "any",
        "bool",
        "dict",
        "enumerate",
        "filter",
        "float",
        "frozenset",
        "int",
        "isinstance",
        "len",
        "list",
        "map",
        "max",
        "min",
        "range",
        "repr",
        "reversed",
        "round",
        "set",
        "sorted",
        "str",
        "sum",
        "tuple",
        "zip",
    )
}

EXPRESSIONS = (
    "Q",
    "F",
    "Value",
    "Count",
    "Sum",
    "Avg",
    "Min",
    "Max",
    "StdDev",
    "Variance",
    "Exists",
    "OuterRef",
    "Subquery",
    "Case",
    "When",
    "Prefetch",
    "Func",
    "ExpressionWrapper",
    "Window",
    "FilteredRelation",
)


def namespace() -> dict[str, Any]:
    """Every name a query can use: the models, their apps, and Django's query vocabulary."""
    scope: dict[str, Any] = {}
    for name in functions.__all__:
        scope[name] = getattr(functions, name)
    for name in EXPRESSIONS:
        if hasattr(models, name):
            scope[name] = getattr(models, name)
    scope.update(
        models=models,
        timezone=timezone,
        datetime=datetime.datetime,
        date=datetime.date,
        time=datetime.time,
        timedelta=datetime.timedelta,
        Decimal=decimal.Decimal,
        uuid=uuid,
        json=json,
    )
    by_app: dict[str, dict[str, type[models.Model]]] = {}
    for model in studio_models():
        by_app.setdefault(model._meta.app_label, {})[model.__name__] = model
    # `blog.Post` always works; a bare `Post` is the model of that name, the first app's when two
    # apps have one — and a model wins over an app or a function that shares its name.
    for label, members in by_app.items():
        scope[label] = SimpleNamespace(**members)
    for members in reversed(list(by_app.values())):
        scope.update(members)
    return scope


@dataclass(frozen=True)
class Kind:
    """What an expression evaluates to, as far as the playground cares."""

    kind: str  # model | manager | queryset | instance | value | object
    model: type[models.Model] | None = None
    obj: Any = None
    # A queryset that annotate()/values() went through may carry names of its own.
    aliased: bool = False


class Source:
    """A query's text with the offsets `ast` leaves implicit."""

    def __init__(self, text: str):
        self.text = text
        self.lines = text.split("\n")
        self.starts: list[int] = []
        position = 0
        for line in self.lines:
            self.starts.append(position)
            position += len(line) + 1

    def offset(self, line: int, column: int) -> int:
        """A character offset from an `ast` position (1-based line, UTF-8 byte column)."""
        if line < 1 or line > len(self.lines):
            return len(self.text)
        text = self.lines[line - 1]
        prefix = text.encode("utf-8")[:column].decode("utf-8", errors="ignore")
        return self.starts[line - 1] + len(prefix)

    def range(self, node: ast.AST) -> dict[str, int]:
        return {
            "start": self.offset(node.lineno, node.col_offset),
            "end": self.offset(node.end_lineno, node.end_col_offset),
        }

    def attribute_range(self, node: ast.Attribute) -> dict[str, int]:
        """The range of the name after the dot."""
        end = self.offset(node.end_lineno, node.end_col_offset)
        return {"start": end - len(node.attr), "end": end}

    def keyword_range(self, node: ast.keyword) -> dict[str, int]:
        start = self.offset(node.lineno, node.col_offset)
        return {"start": start, "end": start + len(node.arg or "")}


def relation_target(model: type[models.Model], name: str) -> tuple[str, type[models.Model]] | None:
    """Following `instance.name`: ('instance' | 'manager', the model on the other side)."""
    for field in model._meta.get_fields():
        if isinstance(field, ForeignObjectRel):
            if field.get_accessor_name() == name and field.related_model is not None:
                return ("manager" if field.multiple else "instance", field.related_model)
        elif field.is_relation and field.name == name and field.related_model is not None:
            return ("manager" if field.many_to_many else "instance", field.related_model)
    return None


def schema_field_name(field: Any) -> str:
    """The name a field goes by in the schema Studio draws."""
    if isinstance(field, ForeignObjectRel):
        return field.get_accessor_name() or field.name
    return field.name


@dataclass
class Step:
    """One hop of a lookup path: the model it was on and the field it named."""

    model: type[models.Model]
    field: Any


def resolve_path(
    model: type[models.Model], parts: list[str]
) -> tuple[list[Step], type[models.Model] | None, list[str], str | None]:
    """Walk `author__profile__bio__icontains` from a model.

    Returns the fields passed, the model reached (None once a plain column ended the walk), the
    parts left over (transforms and the lookup), and the part that names nothing, if any.
    """
    steps: list[Step] = []
    current: type[models.Model] | None = model
    last_field: Any = None
    for index, part in enumerate(parts):
        if current is None:
            # Past a column: only its transforms and lookups can follow.
            known = last_field is not None and (
                last_field.get_lookup(part) is not None
                or last_field.get_transform(part) is not None
            )
            return steps, None, parts[index:], None if known else part
        if part == "pk":
            field = current._meta.pk
        else:
            try:
                field = current._meta.get_field(part)
            except FieldDoesNotExist:
                return steps, current, parts[index:], part
        steps.append(Step(current, field))
        last_field = field
        related = getattr(field, "related_model", None)
        current = related if field.is_relation and related is not None else None
    return steps, current, [], None


class Inference:
    """Types of expressions in a query, with the variables earlier statements assigned."""

    def __init__(self, scope: dict[str, Any] | None = None):
        self.scope = scope if scope is not None else namespace()
        self.variables: dict[str, Kind] = {}

    def assign(self, target: ast.AST, value: ast.AST | None) -> None:
        if isinstance(target, ast.Name):
            kind = self.of(value) if value is not None else None
            if kind is not None:
                self.variables[target.id] = kind
            else:
                self.variables[target.id] = Kind("value")
        elif isinstance(target, (ast.Tuple, ast.List)):
            # `post, created = Post.objects.get_or_create(...)`: the first name is the instance.
            pair = (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Attribute)
                and value.func.attr in ("get_or_create", "update_or_create")
            )
            base = self.of(value.func.value) if pair else None
            for index, element in enumerate(target.elts):
                if isinstance(element, ast.Name):
                    self.variables[element.id] = (
                        Kind("instance", base.model)
                        if pair and index == 0 and base is not None and base.model is not None
                        else Kind("value")
                    )

    def loop(self, target: ast.AST, iterable: ast.AST) -> None:
        """`for post in Post.objects.all():` — the loop variable is an instance."""
        kind = self.of(iterable)
        if isinstance(target, ast.Name):
            if kind is not None and kind.kind in ("queryset", "manager") and not kind.aliased:
                self.variables[target.id] = Kind("instance", kind.model)
            else:
                self.variables[target.id] = Kind("value")

    def known(self, name: str) -> bool:
        return name in self.variables or name in self.scope or name in SAFE_BUILTINS

    def of(self, node: ast.AST | None) -> Kind | None:
        if node is None:
            return None
        if isinstance(node, ast.Name):
            if node.id in self.variables:
                return self.variables[node.id]
            value = self.scope.get(node.id)
            if value is None:
                return None
            if isinstance(value, type) and issubclass(value, models.Model):
                return Kind("model", value)
            return Kind("object", obj=value)
        if isinstance(node, ast.Attribute):
            base = self.of(node.value)
            if base is None:
                return None
            if base.kind == "object":
                value = (
                    getattr(base.obj, node.attr, None) if not node.attr.startswith("_") else None
                )
                if value is None:
                    return None
                if isinstance(value, type) and issubclass(value, models.Model):
                    return Kind("model", value)
                return Kind("object", obj=value)
            if base.model is None:
                return None
            if base.kind == "model":
                managers = {manager.name for manager in base.model._meta.managers}
                if node.attr in managers or node.attr == "objects":
                    return Kind("manager", base.model)
                return None
            if base.kind == "instance":
                target = relation_target(base.model, node.attr)
                if target is not None:
                    return Kind(target[0], target[1])
                return Kind("value")
            return None
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                callee = self.of(func)
                if callee is not None and callee.kind == "model":
                    return Kind("instance", callee.model)
                return Kind("value") if callee is not None else None
            if isinstance(func, ast.Attribute):
                base = self.of(func.value)
                if base is None:
                    return None
                if base.kind in ("manager", "queryset") and base.model is not None:
                    if func.attr in QUERYSET_METHODS:
                        return Kind(
                            "queryset",
                            base.model,
                            aliased=base.aliased or func.attr in ALIASING_METHODS,
                        )
                    if func.attr in INSTANCE_METHODS:
                        return Kind("value") if base.aliased else Kind("instance", base.model)
                    if func.attr in VALUE_METHODS or func.attr in WRITE_METHODS:
                        return Kind("value", base.model)
                    # A method of the project's own manager: a queryset is the likeliest answer.
                    return Kind("queryset", base.model, aliased=True)
                if base.kind == "instance":
                    return Kind("value", base.model)
                return Kind("value")
            return None
        if isinstance(node, ast.Subscript):
            base = self.of(node.value)
            if base is not None and base.kind in ("manager", "queryset"):
                if isinstance(node.slice, ast.Slice):
                    return Kind("queryset", base.model, aliased=base.aliased)
                return Kind("value") if base.aliased else Kind("instance", base.model)
            return Kind("value") if base is not None else None
        if isinstance(node, ast.BinOp):
            # `qs1 | qs2`, `qs1 & qs2`
            left = self.of(node.left)
            if left is not None and left.kind == "queryset":
                return left
            return Kind("value")
        if isinstance(node, ast.Constant):
            return Kind("value")
        return None


def chain_methods(node: ast.AST) -> list[str]:
    """The method names of `a.b().c().d()`, innermost first."""
    out: list[str] = []
    current = node
    while True:
        if isinstance(current, ast.Call) and isinstance(current.func, ast.Attribute):
            out.append(current.func.attr)
            current = current.func.value
        elif isinstance(current, ast.Subscript) or isinstance(current, ast.Attribute):
            current = current.value
        else:
            break
    out.reverse()
    return out


def parse(text: str) -> tuple[ast.Module | None, dict[str, Any] | None]:
    """The syntax tree of a query, or where its syntax breaks."""
    source = Source(text)
    try:
        return ast.parse(text), None
    except SyntaxError as error:
        # SyntaxError counts columns in characters, from 1.
        line = min(max(error.lineno or 1, 1), len(source.starts))
        start = min(source.starts[line - 1] + max((error.offset or 1) - 1, 0), len(text))
        end = start + 1
        if error.end_lineno and error.end_offset and 1 <= error.end_lineno <= len(source.starts):
            end = max(source.starts[error.end_lineno - 1] + error.end_offset - 1, start + 1)
        end = min(end, max(len(text), start + 1))
        return None, {"message": f"SyntaxError: {error.msg}", "range": {"start": start, "end": end}}
