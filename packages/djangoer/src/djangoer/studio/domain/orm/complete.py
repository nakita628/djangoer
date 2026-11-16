"""What can be typed next in a query, what a name means, and what a call takes.

The text before the cursor is rarely valid Python, so the cursor's surroundings are read with a
small scanner (which bracket is open, is this a string, what precedes the dot) and only the
complete expression found there is handed to `ast`.
"""

from __future__ import annotations

import ast
import inspect
import re
from dataclasses import dataclass
from typing import Any

from django.db import models
from django.db.models.fields.related import ForeignObjectRel
from django.db.models.query import QuerySet

from ...inputs import CompletionAt, QueryAt
from .infer import (
    FIELD_METHODS,
    INSTANCE_METHODS,
    LOOKUP_METHODS,
    PATH_METHODS,
    QUERYSET_METHODS,
    SAFE_BUILTINS,
    VALUE_METHODS,
    Inference,
    Kind,
    Source,
    parse,
    resolve_path,
)

WORD = re.compile(r"[A-Za-z_][A-Za-z_0-9]*$")
CLOSERS = {")": "(", "]": "[", "}": "{"}

LOOKUP_DOCS = {
    "exact": "Exact match. `None` matches SQL NULL.",
    "iexact": "Case-insensitive exact match.",
    "contains": "Case-sensitive containment test (`LIKE '%x%'`).",
    "icontains": "Case-insensitive containment test.",
    "in": "In a given iterable, or a queryset.",
    "gt": "Greater than.",
    "gte": "Greater than or equal to.",
    "lt": "Less than.",
    "lte": "Less than or equal to.",
    "startswith": "Case-sensitive starts-with.",
    "istartswith": "Case-insensitive starts-with.",
    "endswith": "Case-sensitive ends-with.",
    "iendswith": "Case-insensitive ends-with.",
    "range": "Range test (inclusive): `(start, end)`.",
    "isnull": "`True` for SQL NULL, `False` for NOT NULL.",
    "regex": "Case-sensitive regular expression match.",
    "iregex": "Case-insensitive regular expression match.",
    "date": "Casts a datetime to a date.",
    "year": "The year of a date or datetime.",
    "month": "The month of a date or datetime.",
    "day": "The day of a date or datetime.",
    "week_day": "The day of the week: 1 (Sunday) to 7 (Saturday).",
}


@dataclass
class Bracket:
    char: str
    position: int


@dataclass
class Cursor:
    """Where the cursor is: the open brackets around it and the string it is in, if any."""

    prefix: str
    stack: list[Bracket]
    string_start: int | None

    @property
    def in_string(self) -> bool:
        return self.string_start is not None

    @property
    def string_text(self) -> str:
        return self.prefix[self.string_start + 1 :] if self.string_start is not None else ""


def scan(prefix: str) -> Cursor:
    stack: list[Bracket] = []
    string_start: int | None = None
    quote = ""
    index = 0
    while index < len(prefix):
        char = prefix[index]
        if string_start is not None:
            if char == "\\":
                index += 2
                continue
            if char == quote or (char == "\n" and len(quote) == 1):
                string_start = None
        elif char in "\"'":
            string_start = index
            quote = char
        elif char == "#":
            newline = prefix.find("\n", index)
            if newline == -1:
                break
            index = newline
        elif char in "([{":
            stack.append(Bracket(char, index))
        elif char in CLOSERS and stack and stack[-1].char == CLOSERS[char]:
            stack.pop()
        index += 1
    return Cursor(prefix, stack, string_start)


def expression_before(text: str, end: int) -> str:
    """The expression that ends at `end`: names, dots and whole bracket groups, read backwards."""
    index = end
    while index > 0:
        char = text[index - 1]
        if char in ")]}":
            depth = 0
            position = index - 1
            while position >= 0:
                if text[position] in ")]}":
                    depth += 1
                elif text[position] in "([{":
                    depth -= 1
                    if depth == 0:
                        break
                position -= 1
            if position < 0:
                break
            index = position
        elif char.isalnum() or char in "_.":
            index -= 1
        elif char in " \t\n":
            # A chain broken over lines: the space is part of it when a dot is on either side.
            left = index - 1
            while left > 0 and text[left - 1] in " \t\n":
                left -= 1
            if text[index : index + 1] == "." or (left > 0 and text[left - 1] == "."):
                index = left
            else:
                break
        else:
            break
    return text[index:end].strip()


def _inference(text: str, statement_start: int) -> Inference:
    """The variables the statements before this one assigned."""
    inference = Inference()
    tree, _error = parse(text[:statement_start])
    if tree is None:
        return inference
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                inference.assign(target, node.value)
        elif isinstance(node, ast.For):
            inference.loop(node.target, node.iter)
    return inference


def _statement_start(prefix: str, cursor: Cursor) -> int:
    """The start of the line the statement around the cursor begins on."""
    anchor = cursor.stack[0].position if cursor.stack else len(prefix)
    return prefix.rfind("\n", 0, anchor) + 1


def _kind_of(inference: Inference, expression: str) -> Kind | None:
    if not expression:
        return None
    try:
        node = ast.parse(f"({expression})", mode="eval").body
    except SyntaxError:
        return None
    return inference.of(node)


def _item(label: str, kind: str, rank: int, insert: str | None = None) -> dict[str, Any]:
    return {"label": label, "kind": kind, "sortText": f"{rank}{label}", "insertText": insert}


def _field_items(model: type[models.Model], rank: int = 0) -> list[dict[str, Any]]:
    """Every name a lookup can start with: columns, relations and the reverse relations."""
    items = [_item("pk", "field", rank + 1)]
    for field in model._meta.get_fields():
        if isinstance(field, ForeignObjectRel):
            items.append(_item(field.name, "relation", rank + 1))
            continue
        items.append(_item(field.name, "relation" if field.is_relation else "field", rank))
        attname = getattr(field, "attname", None)
        if attname and attname != field.name:
            items.append(_item(attname, "field", rank + 1))
    return items


def _lookup_items(field: Any, rank: int = 0) -> list[dict[str, Any]]:
    names = sorted(name for name in field.get_lookups() if not name.startswith("_"))
    common = ("exact", "in", "isnull", "gt", "gte", "lt", "lte", "icontains", "contains")
    return [_item(name, "lookup", rank if name in common else rank + 1) for name in names]


def _path_items(model: type[models.Model], typed: str, *, lookups: bool) -> list[dict[str, Any]]:
    """Completions for the last segment of `author__profile__` typed so far."""
    parts = typed.split("__")[:-1]
    if not parts:
        return _field_items(model)
    steps, reached, _rest, unknown = resolve_path(model, parts)
    if unknown is not None:
        return []
    if reached is not None:
        return _field_items(reached)
    if lookups and steps:
        return _lookup_items(steps[-1].field)
    return []


def _instance_items(model: type[models.Model]) -> list[dict[str, Any]]:
    items = [_item("pk", "field", 1)]
    for field in model._meta.get_fields():
        if isinstance(field, ForeignObjectRel):
            accessor = field.get_accessor_name()
            if accessor:
                items.append(_item(accessor, "relation", 1))
            continue
        items.append(_item(field.name, "relation" if field.is_relation else "field", 0))
        attname = getattr(field, "attname", None)
        if attname and attname != field.name:
            items.append(_item(attname, "field", 1))
    for name in ("save", "delete", "refresh_from_db", "full_clean"):
        items.append(_item(name, "method", 2))
    for name, value in inspect.getmembers(model):
        defined_here = name in vars(model) or any(
            name in vars(base) for base in model.__mro__[1:] if base is not models.Model
        )
        if (
            not name.startswith("_")
            and defined_here
            and (inspect.isfunction(value) or isinstance(value, property))
            and not any(item["label"] == name for item in items)
        ):
            items.append(_item(name, "method" if inspect.isfunction(value) else "property", 2))
    return items


def _queryset_items(model: type[models.Model]) -> list[dict[str, Any]]:
    items = [
        _item(name, "method", rank)
        for rank, group in enumerate((QUERYSET_METHODS, INSTANCE_METHODS, VALUE_METHODS))
        for name in group
    ]
    known = {item["label"] for item in items}
    manager = model._default_manager
    base = set(dir(models.Manager))
    # What the project's own manager or queryset adds.
    for name in dir(manager):
        if name.startswith("_") or name in base or name in known:
            continue
        if callable(getattr(manager, name, None)):
            items.append(_item(name, "method", 0))
    return items


def _object_items(obj: Any) -> list[dict[str, Any]]:
    items = []
    for name in dir(obj):
        if name.startswith("_"):
            continue
        value = getattr(obj, name, None)
        kind = "class" if inspect.isclass(value) else "function" if callable(value) else "property"
        items.append(_item(name, kind, 0))
    return items


def _member_items(kind: Kind | None) -> list[dict[str, Any]]:
    if kind is None:
        return []
    if kind.kind == "object":
        return _object_items(kind.obj)
    if kind.model is None:
        return []
    if kind.kind == "model":
        managers = [_item(manager.name, "manager", 0) for manager in kind.model._meta.managers]
        return managers or [_item("objects", "manager", 0)]
    if kind.kind in ("manager", "queryset"):
        return _queryset_items(kind.model)
    if kind.kind == "instance":
        return _instance_items(kind.model)
    return []


def _scope_items(inference: Inference) -> list[dict[str, Any]]:
    items = [_item(name, "variable", 0) for name in inference.variables]
    for name, value in inference.scope.items():
        if isinstance(value, type) and issubclass(value, models.Model):
            items.append(_item(name, "model", 1))
        elif inspect.isclass(value):
            items.append(_item(name, "class", 3))
        elif callable(value):
            items.append(_item(name, "function", 3))
        else:
            items.append(_item(name, "module", 2))
    items.extend(_item(name, "function", 4) for name in SAFE_BUILTINS)
    items.extend(_item(name, "value", 4) for name in ("True", "False", "None"))
    items.extend(_item(name, "keyword", 4) for name in ("for", "in", "if", "not", "and", "or"))
    return items


@dataclass
class CallSite:
    """The innermost call the cursor is inside: who is called, on what, and which argument."""

    callee: str
    method: str | None
    receiver: Kind | None
    name: str | None
    position: int
    argument: int


def _call_sites(prefix: str, cursor: Cursor, inference: Inference) -> list[CallSite]:
    """The calls around the cursor, innermost first."""
    sites: list[CallSite] = []
    for bracket in reversed(cursor.stack):
        if bracket.char != "(":
            continue
        callee = expression_before(prefix, bracket.position)
        if not callee:
            continue
        try:
            node = ast.parse(f"({callee})", mode="eval").body
        except SyntaxError:
            continue
        inside = prefix[bracket.position + 1 :]
        argument = len(_top_level_commas(inside))
        if isinstance(node, ast.Attribute):
            sites.append(
                CallSite(
                    callee, node.attr, inference.of(node.value), None, bracket.position, argument
                )
            )
        elif isinstance(node, ast.Name):
            sites.append(
                CallSite(callee, None, inference.of(node), node.id, bracket.position, argument)
            )
    return sites


def _top_level_commas(text: str) -> list[int]:
    out = []
    depth = 0
    in_string: str | None = None
    for index, char in enumerate(text):
        if in_string:
            if char == in_string and text[index - 1] != "\\":
                in_string = None
        elif char in "\"'":
            in_string = char
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "," and depth == 0:
            out.append(index)
    return out


def _query_model(sites: list[CallSite]) -> tuple[type[models.Model], str] | None:
    """The model whose fields are being named, through any Q() or F() in between."""
    for site in sites:
        if site.method is None:
            if site.name in ("Q", "F", "OuterRef", "Count", "Sum", "Avg", "Min", "Max", "When"):
                continue
            if site.receiver is not None and site.receiver.kind == "model":
                return site.receiver.model, "__init__"
            return None
        if site.receiver is not None and site.receiver.model is not None:
            if site.receiver.kind in ("manager", "queryset"):
                return site.receiver.model, site.method
            return None
    return None


def complete(input: QueryAt):
    text, offset = input.query, input.offset
    prefix = text[: max(0, min(offset, len(text)))]
    cursor = scan(prefix)
    inference = _inference(text, _statement_start(prefix, cursor))
    sites = _call_sites(prefix, cursor, inference)
    target = _query_model(sites)

    if cursor.in_string:
        if target is None or not sites:
            return {"items": []}
        model, method = target
        innermost = sites[0]
        typed = cursor.string_text.lstrip("-+")
        in_expression = innermost.method is None and innermost.name in (
            "F",
            "OuterRef",
            "Count",
            "Sum",
            "Avg",
            "Min",
            "Max",
        )
        if in_expression or method in PATH_METHODS:
            return {"items": _path_items(model, typed, lookups=in_expression)}
        return {"items": []}

    word = WORD.search(prefix)
    typed = word.group() if word else ""
    before = prefix[: len(prefix) - len(typed)]
    if before.rstrip().endswith("."):
        receiver = expression_before(before, len(before.rstrip()) - 1)
        return {"items": _member_items(_kind_of(inference, receiver))}

    items: list[dict[str, Any]] = []
    if target is not None and sites:
        model, method = target
        innermost = sites[0]
        through_q = innermost.method is None and innermost.name in ("Q", "When")
        # A keyword argument starts right after `(` or `,`; after `=` a value is being typed.
        at_keyword = before.rstrip().endswith(("(", ","))
        if at_keyword and (through_q or innermost.method in LOOKUP_METHODS):
            items = _path_items(model, typed, lookups=True)
        elif at_keyword and (method in FIELD_METHODS or method == "__init__"):
            items = _path_items(model, typed.split("__")[0], lookups=False)
        if "__" in typed:
            return {"items": items}
    return {
        "items": [
            *items,
            *[{**item, "sortText": "5" + item["sortText"]} for item in _scope_items(inference)],
        ]
    }


# ---------------------------------------------------------------------------
# What a name means
# ---------------------------------------------------------------------------


def _signature(func: Any, name: str) -> str:
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return f"{name}(...)"
    parameters = [p for p in signature.parameters.values() if p.name not in ("self", "cls")]
    return f"{name}({', '.join(str(parameter) for parameter in parameters)})"


def _doc(obj: Any) -> str | None:
    doc = inspect.getdoc(obj)
    return doc or None


def _field_summary(field: Any) -> str:
    if isinstance(field, ForeignObjectRel):
        kind = "reverse relation" if field.multiple else "reverse one-to-one"
        return f"{field.name}: {kind} to {field.related_model.__name__}"
    options = []
    try:
        _name, _path, _args, kwargs = field.deconstruct()
        for key, value in kwargs.items():
            if key == "to":
                continue
            options.append(f"{key}={getattr(value, '__name__', None) or repr(value)}")
    except Exception:  # noqa: BLE001
        options = []
    target = (
        f"{field.related_model.__name__}, " if field.is_relation and field.related_model else ""
    )
    body = f"{target}{', '.join(options)}".rstrip(", ")
    return f"{field.name}: {type(field).__name__}({body})"


def _model_summary(model: type[models.Model]) -> str:
    lines = [f"class {model.__name__}(models.Model):"]
    for field in model._meta.get_fields():
        if isinstance(field, ForeignObjectRel):
            continue
        summary = _field_summary(field)
        name, _, rest = summary.partition(": ")
        lines.append(f"    {name} = {rest}")
    return "\n".join(lines)


def _describe_member(kind: Kind | None, name: str) -> tuple[str | None, str | None]:
    """(detail, documentation) of `name` on something of this kind."""
    if kind is None:
        return None, None
    if kind.kind == "object":
        value = getattr(kind.obj, name, None) if not name.startswith("_") else None
        if value is None:
            return None, None
        return _describe_value(name, value)
    if kind.model is None:
        return None, None
    if kind.kind in ("manager", "queryset"):
        method = getattr(QuerySet, name, None) or getattr(
            type(kind.model._default_manager), name, None
        )
        if method is None:
            return None, None
        return _signature(method, name), _doc(method)
    if kind.kind == "instance":
        if name == "pk":
            return f"pk: {type(kind.model._meta.pk).__name__}", "The primary key."
        for field in kind.model._meta.get_fields():
            accessor = (
                field.get_accessor_name() if isinstance(field, ForeignObjectRel) else field.name
            )
            if name in (accessor, getattr(field, "attname", None)):
                help_text = getattr(field, "help_text", "") or None
                return _field_summary(field), str(help_text) if help_text else None
        value = getattr(kind.model, name, None)
        if callable(value):
            return _signature(value, name), _doc(value)
        return None, None
    if kind.kind == "model" and name in {m.name for m in kind.model._meta.managers} | {"objects"}:
        return f"{name}: Manager[{kind.model.__name__}]", "The manager: where every query starts."
    return None, None


def _describe_value(name: str, value: Any) -> tuple[str | None, str | None]:
    if isinstance(value, type) and issubclass(value, models.Model):
        return _model_summary(value), _doc_of_model(value)
    if inspect.isclass(value):
        return f"class {_signature(value, name)}", _doc(value)
    if callable(value):
        return _signature(value, name), _doc(value)
    return f"{name}: {type(value).__name__}", None


def _doc_of_model(model: type[models.Model]) -> str | None:
    doc = inspect.cleandoc(model.__doc__ or "")
    return None if not doc or doc.startswith(f"{model.__name__}(") else doc


def _describe_path(
    model: type[models.Model], text: str, upto: int
) -> tuple[str | None, str | None]:
    """The part of a lookup path under the cursor (`upto` characters into it)."""
    parts = text.split("__")
    position = 0
    index = 0
    for index, part in enumerate(parts):  # noqa: B007
        if upto <= position + len(part):
            break
        position += len(part) + 2
    steps, _reached, rest, unknown = resolve_path(model, parts[: index + 1])
    if unknown is not None:
        return None, None
    if rest:
        name = rest[-1]
        return f"{name} (lookup)", LOOKUP_DOCS.get(name)
    if not steps:
        return None, None
    field = steps[-1].field
    help_text = getattr(field, "help_text", "") or None
    return _field_summary(field), str(help_text) if help_text else None


def detail(input: CompletionAt):
    """`ClientCompletionDetail` for one item of the list `complete` gave at the same place."""
    text, offset, name = input.query, input.offset, input.name
    prefix = text[: max(0, min(offset, len(text)))]
    cursor = scan(prefix)
    inference = _inference(text, _statement_start(prefix, cursor))
    sites = _call_sites(prefix, cursor, inference)
    target = _query_model(sites)
    word = WORD.search(prefix)
    typed = word.group() if word and not cursor.in_string else ""
    before = prefix[: len(prefix) - len(typed)]
    found: tuple[str | None, str | None] = (None, None)
    if not cursor.in_string and before.rstrip().endswith("."):
        receiver = expression_before(before, len(before.rstrip()) - 1)
        found = _describe_member(_kind_of(inference, receiver), name)
    elif target is not None:
        typed_path = cursor.string_text.lstrip("-+") if cursor.in_string else typed
        parts = [*typed_path.split("__")[:-1], name]
        path = "__".join(parts)
        found = _describe_path(target[0], path, len(path))
    if found == (None, None) and name in inference.scope:
        found = _describe_value(name, inference.scope[name])
    return {"detail": found[0], "documentation": found[1]}


def _markdown(detail_text: str | None, documentation: str | None) -> str | None:
    if detail_text is None and documentation is None:
        return None
    parts = []
    if detail_text:
        parts.append(f"```python\n{detail_text}\n```")
    if documentation:
        parts.append(documentation)
    return "\n\n".join(parts)


def hover(input: QueryAt):
    """`ClientHover`: the name under the cursor, described from the whole query's syntax tree."""
    text, offset = input.query, input.offset
    empty = {"contents": None, "range": None}
    tree, _error = parse(text)
    if tree is None:
        return empty
    source = Source(text)
    inference = Inference()
    best: tuple[int, dict[str, int], tuple[str | None, str | None]] | None = None

    def consider(span: dict[str, int], described: tuple[str | None, str | None]) -> None:
        nonlocal best
        if not (span["start"] <= offset <= span["end"]) or described == (None, None):
            return
        size = span["end"] - span["start"]
        if best is None or size < best[0]:
            best = (size, span, described)

    def model_for(call: ast.Call) -> type[models.Model] | None:
        if isinstance(call.func, ast.Attribute):
            receiver = inference.of(call.func.value)
            if receiver is not None and receiver.kind in ("manager", "queryset"):
                return receiver.model
        elif isinstance(call.func, ast.Name):
            callee = inference.of(call.func)
            if callee is not None and callee.kind == "model":
                return callee.model
        return None

    def walk(node: ast.AST, context: type[models.Model] | None) -> None:
        if isinstance(node, ast.Assign):
            walk(node.value, context)
            for target in node.targets:
                inference.assign(target, node.value)
            return
        if isinstance(node, ast.For):
            walk(node.iter, context)
            inference.loop(node.target, node.iter)
            for statement in node.body:
                walk(statement, context)
            return
        if isinstance(node, ast.Name):
            if node.id in inference.scope and node.id not in inference.variables:
                consider(source.range(node), _describe_value(node.id, inference.scope[node.id]))
            return
        if isinstance(node, ast.Attribute):
            consider(
                source.attribute_range(node),
                _describe_member(inference.of(node.value), node.attr),
            )
            walk(node.value, context)
            return
        if isinstance(node, ast.Call):
            model = model_for(node)
            is_expression = isinstance(node.func, ast.Name) and node.func.id in ("Q", "F", "When")
            inner = model if model is not None else context
            walk(node.func, context)
            names_fields = model is not None or (is_expression and context is not None)
            method = node.func.attr if isinstance(node.func, ast.Attribute) else None
            for keyword in node.keywords:
                if (
                    keyword.arg
                    and names_fields
                    and inner is not None
                    and (method is None or method in LOOKUP_METHODS or method in FIELD_METHODS)
                ):
                    span = source.keyword_range(keyword)
                    consider(span, _describe_path(inner, keyword.arg, offset - span["start"]))
                walk(keyword.value, inner)
            for argument in node.args:
                is_path = isinstance(argument, ast.Constant) and isinstance(argument.value, str)
                if is_path and inner is not None and (method in PATH_METHODS or is_expression):
                    span = source.range(argument)
                    stripped = argument.value.lstrip("-+")
                    lead = 1 + len(argument.value) - len(stripped)
                    consider(span, _describe_path(inner, stripped, offset - span["start"] - lead))
                else:
                    walk(argument, inner)
            return
        for child in ast.iter_child_nodes(node):
            walk(child, context)

    walk(tree, None)
    if best is None:
        return empty
    return {"contents": _markdown(*best[2]), "range": best[1]}


def signature(input: QueryAt):
    """`ClientSignatureHelp` for the call the cursor is inside."""
    text, offset = input.query, input.offset
    empty = {"signatures": [], "activeSignature": 0, "activeParameter": 0}
    prefix = text[: max(0, min(offset, len(text)))]
    cursor = scan(prefix)
    inference = _inference(text, _statement_start(prefix, cursor))
    sites = _call_sites(prefix, cursor, inference)
    if not sites:
        return empty
    site = sites[0]
    func: Any = None
    name = site.method or site.name or ""
    documentation: str | None = None
    parameters: list[str] | None = None
    if site.method is not None and site.receiver is not None:
        if site.receiver.kind in ("manager", "queryset") and site.receiver.model is not None:
            func = getattr(QuerySet, name, None) or getattr(
                type(site.receiver.model._default_manager), name, None
            )
        elif site.receiver.kind == "instance" and site.receiver.model is not None:
            func = getattr(site.receiver.model, name, None)
        elif site.receiver.kind == "object":
            func = getattr(site.receiver.obj, name, None) if not name.startswith("_") else None
    elif site.receiver is not None and site.receiver.kind == "model" and site.receiver.model:
        # A model's constructor takes its fields.
        parameters = [
            f"{field.name}=..."
            for field in site.receiver.model._meta.get_fields()
            if not isinstance(field, ForeignObjectRel) and not field.many_to_many
        ]
        documentation = _doc_of_model(site.receiver.model)
    elif site.receiver is not None and site.receiver.kind == "object":
        func = site.receiver.obj
    if parameters is None:
        if func is None or not callable(func):
            return empty
        try:
            parsed = inspect.signature(func)
        except (TypeError, ValueError):
            return empty
        parameters = [str(p) for p in parsed.parameters.values() if p.name not in ("self", "cls")]
        documentation = _doc(func)
    return {
        "signatures": [
            {
                "label": f"{name}({', '.join(parameters)})",
                "documentation": documentation,
                "parameters": [{"label": label, "documentation": None} for label in parameters],
            }
        ],
        "activeSignature": 0,
        "activeParameter": min(site.argument, max(len(parameters) - 1, 0)),
    }
