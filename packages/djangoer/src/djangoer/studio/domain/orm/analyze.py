"""A query before it runs: the calls it makes, the models and fields it touches, its mistakes."""

from __future__ import annotations

import ast
from typing import Any

from django.db import models

from ...inputs import Query
from ..schema import Names, names
from .infer import (
    ALIASING_METHODS,
    FIELD_METHODS,
    FORBIDDEN_NODES,
    INSTANCE_METHODS,
    INSTANCE_WRITES,
    LOOKUP_METHODS,
    PATH_METHODS,
    QUERYSET_METHODS,
    WRITE_METHODS,
    Inference,
    Kind,
    Source,
    chain_methods,
    parse,
    resolve_path,
    schema_field_name,
)

# Expressions that name fields of the queryset they are used on.
PATH_EXPRESSIONS = frozenset(
    {"Q", "F", "OuterRef", "Count", "Sum", "Avg", "Min", "Max", "StdDev", "Variance"}
)


# Methods of a manager or a queryset that only read. `raw` is left out: its SQL can be anything.
READ_METHODS = (
    frozenset(QUERYSET_METHODS) - {"raw"}
    | frozenset(INSTANCE_METHODS) - {"create"}
    | {"count", "exists", "aggregate", "in_bulk", "iterator", "explain", "contains"}
)


# What `inspect` says for the server alone: not part of the analysis a page is sent.
SERVER_ONLY = frozenset({"errors", "pure"})


class Analyzer(ast.NodeVisitor):
    def __init__(self, text: str, known: Names | None = None):
        self.source = Source(text)
        self.names = known or names()
        self.inference = Inference()
        self.calls: list[dict[str, Any]] = []
        self.touched: dict[str, list[str]] = {}
        self.diagnostics: list[dict[str, Any]] = []
        self.errors: list[dict[str, Any]] = []
        # The model the expression being read is about, for Q() and F() nested in its arguments.
        self.context: list[tuple[type[models.Model], bool]] = []
        self.chained: set[int] = set()
        # Whether running the query can only read: nothing but known read methods is called.
        self.pure = True

    # -- bookkeeping ---------------------------------------------------------

    def touch(self, model: type[models.Model], field: str | None = None) -> None:
        name = self.names.of(model)
        if name is None:
            return
        fields = self.touched.setdefault(name, [])
        if field is not None and field not in fields:
            fields.append(field)

    def error(self, message: str, span: dict[str, int]) -> None:
        self.errors.append({"message": message, "range": span})

    def warn(self, message: str, span: dict[str, int]) -> None:
        self.diagnostics.append({"message": message, "range": span})

    def path(
        self, model: type[models.Model], text: str, span: dict[str, int], aliased: bool
    ) -> None:
        """Touch every field a lookup path names; say so when a part names nothing."""
        parts = [part for part in text.split("__") if part]
        if not parts:
            return
        steps, _reached, _rest, unknown = resolve_path(model, parts)
        for step in steps:
            self.touch(step.model, schema_field_name(step.field))
            related = getattr(step.field, "related_model", None)
            if step.field.is_relation and related is not None:
                self.touch(related)
        if unknown is not None and not (aliased and not steps):
            where = steps[-1].field.name if steps and _reached is None else None
            if where is not None:
                self.warn(f'Unsupported lookup "{unknown}" for field "{where}"', span)
            else:
                on = (_reached or model).__name__
                self.warn(f'Cannot resolve "{unknown}" into a field of {on}', span)

    # -- statements ----------------------------------------------------------

    def generic_visit(self, node: ast.AST) -> None:
        for forbidden, message in FORBIDDEN_NODES:
            if isinstance(node, forbidden):
                self.error(message, self.source.range(node))
                return
        super().generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        for target in node.targets:
            self.inference.assign(target, node.value)
            if not isinstance(target, (ast.Name, ast.Tuple, ast.List)):
                self.visit(target)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self.visit(node.value)
        self.inference.assign(node.target, node.value)

    def visit_For(self, node: ast.For) -> None:
        self.visit(node.iter)
        self.inference.loop(node.target, node.iter)
        for statement in [*node.body, *node.orelse]:
            self.visit(statement)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.visit(node.iter)
        self.inference.loop(node.target, node.iter)
        for condition in node.ifs:
            self.visit(condition)

    def _comprehension(self, node: Any, parts: list[ast.AST]) -> None:
        # The generators bind the names the element uses, so they are read first.
        for generator in node.generators:
            self.visit(generator)
        for part in parts:
            self.visit(part)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._comprehension(node, [node.elt])

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._comprehension(node, [node.elt])

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._comprehension(node, [node.elt])

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._comprehension(node, [node.key, node.value])

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for argument in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
            self.inference.variables[argument.arg] = Kind("value")
        self.visit(node.body)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.visit(node.value)
        self.inference.assign(node.target, node.value)

    # -- expressions ---------------------------------------------------------

    def visit_Name(self, node: ast.Name) -> None:
        if node.id.startswith("__"):
            self.error(f'"{node.id}" is not available here', self.source.range(node))
        elif isinstance(node.ctx, ast.Load) and not self.inference.known(node.id):
            self.error(f'Unknown name "{node.id}"', self.source.range(node))
        kind = self.inference.of(node)
        if kind is not None and kind.kind == "model" and kind.model is not None:
            self.touch(kind.model)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("_"):
            self.error(
                f'"{node.attr}" is private: names that start with an underscore are not available here',
                self.source.attribute_range(node),
            )
        base = self.inference.of(node.value)
        if base is not None and base.kind == "instance" and base.model is not None:
            self._instance_attribute(base.model, node)
        if base is not None and base.kind == "model" and base.model is not None:
            reached = self.inference.of(node)
            if reached is None and not hasattr(base.model, node.attr):
                self.warn(
                    f'{base.model.__name__} has no attribute "{node.attr}"',
                    self.source.attribute_range(node),
                )
        self.visit(node.value)
        # A chain that ends on a manager (`Post.objects`, `post.comments`) reads its rows.
        reached = self.inference.of(node)
        if id(node) not in self.chained and reached is not None and reached.kind == "manager":
            self._record(node)

    def _instance_attribute(self, model: type[models.Model], node: ast.Attribute) -> None:
        for field in model._meta.get_fields():
            accessor = schema_field_name(field)
            attname = getattr(field, "attname", None)
            if node.attr in (accessor, attname):
                self.touch(model, attname if node.attr == attname and attname else accessor)
                return

    def visit_Subscript(self, node: ast.Subscript) -> None:
        self._mark_chain(node.value)
        self.visit(node.value)
        self.visit(node.slice)
        if id(node) not in self.chained:
            self._record(node)

    def _mark_chain(self, node: ast.AST) -> None:
        """The inner links of a chain are part of the call recorded at its end."""
        current: ast.AST | None = node
        while current is not None:
            self.chained.add(id(current))
            if isinstance(current, ast.Call):
                current = current.func
            elif isinstance(current, (ast.Attribute, ast.Subscript)):
                current = current.value
            else:
                current = None

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        receiver: Kind | None = None
        method: str | None = None
        if isinstance(func, ast.Attribute):
            receiver = self.inference.of(func.value)
            method = func.attr
        elif isinstance(func, ast.Name):
            callee = self.inference.of(func)
            if callee is not None and callee.kind == "model" and callee.model is not None:
                # `Post(title=...)`: the keywords are the model's fields.
                self._fields(callee.model, node, aliased=False)
        if isinstance(func, ast.Attribute):
            if receiver is not None and receiver.kind in ("manager", "queryset"):
                self.pure = self.pure and func.attr in READ_METHODS
            elif receiver is not None and receiver.kind in ("instance", "model"):
                # A method of the project's own: it may save, send or call out.
                self.pure = False
            elif receiver is None or receiver.kind == "value":
                self.pure = self.pure and func.attr not in WRITE_METHODS
        elif not isinstance(func, ast.Name):
            self.pure = False
        self._mark_chain(func)
        self.visit(func)

        model = receiver.model if receiver is not None else None
        on_query = receiver is not None and receiver.kind in ("manager", "queryset")
        if on_query and model is not None and method is not None:
            aliased = receiver.aliased or bool(
                ALIASING_METHODS.intersection(chain_methods(func.value))
            )
            self.context.append((model, aliased))
            self._arguments(model, method, node, aliased)
            for argument in [*node.args, *[keyword.value for keyword in node.keywords]]:
                self.visit(argument)
            self.context.pop()
        else:
            if isinstance(func, ast.Name) and func.id in PATH_EXPRESSIONS and self.context:
                self._expression(func.id, node)
            for argument in [*node.args, *[keyword.value for keyword in node.keywords]]:
                self.visit(argument)
        if id(node) not in self.chained:
            self._record(node)

    def _expression(self, name: str, node: ast.Call) -> None:
        """Q(field__lookup=...) and F("field") inside a call on a queryset."""
        model, aliased = self.context[-1]
        if name == "Q":
            for keyword in node.keywords:
                if keyword.arg is not None:
                    self.path(model, keyword.arg, self.source.keyword_range(keyword), aliased)
        else:
            for argument in node.args:
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    self.path(model, argument.value, self.source.range(argument), aliased)

    def _fields(self, model: type[models.Model], node: ast.Call, aliased: bool) -> None:
        for keyword in node.keywords:
            if keyword.arg is None or keyword.arg == "defaults":
                continue
            self.path(model, keyword.arg, self.source.keyword_range(keyword), aliased)

    def _arguments(self, model: type[models.Model], method: str, node: ast.Call, aliased: bool):
        if method in LOOKUP_METHODS or method in FIELD_METHODS:
            self._fields(model, node, aliased)
        if method in PATH_METHODS:
            for argument in node.args:
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    text = argument.value.lstrip("-+")
                    if text and text != "?":
                        self.path(model, text, self.source.range(argument), aliased)

    def _record(self, node: ast.AST) -> None:
        """One entry per chain: the model it starts from and the last thing done to it."""
        methods = chain_methods(node)
        root: ast.AST = node
        while True:
            if isinstance(root, ast.Call):
                root = root.func
            elif isinstance(root, (ast.Attribute, ast.Subscript)):
                root = root.value
            else:
                break
        kind = self.inference.of(node)
        base = self.inference.of(root)
        if base is None or base.kind not in ("model", "instance", "queryset", "manager"):
            return
        # The model the chain ends on, which a relation may have changed along the way.
        model = (kind.model if kind is not None and kind.model is not None else None) or base.model
        receiver = None
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            receiver = self.inference.of(node.func.value)
            if receiver is not None and receiver.model is not None:
                model = receiver.model
        if model is None:
            return
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            operation = "create instance"
        elif methods:
            operation = methods[-1]
        elif isinstance(node, ast.Attribute):
            operation = node.attr
        else:
            operation = "all"
        on_instance = receiver is not None and receiver.kind == "instance"
        write = bool(WRITE_METHODS.intersection(methods)) and not (
            on_instance and methods[-1] not in INSTANCE_WRITES and len(methods) == 1
        )
        name = self.names.of(model)
        if name is None:
            return
        self.touch(model)
        self.calls.append(
            {
                "model": name,
                "operation": operation,
                "write": write,
                "range": self.source.range(node),
            }
        )


def inspect(text: str) -> dict[str, Any]:
    """Everything read from a query: the analysis the page shows, with `errors` (what stops
    it from running) and `pure` (whether running it can only read) for the server itself."""
    tree, syntax_error = parse(text)
    if tree is None:
        return {
            "calls": [],
            "transaction": False,
            "touched": [],
            "diagnostics": [syntax_error] if syntax_error else [],
            "errors": [syntax_error] if syntax_error else [],
            "pure": False,
        }
    analyzer = Analyzer(text)
    analyzer.visit(tree)
    writes = sum(1 for call in analyzer.calls if call["write"])
    return {
        "calls": sorted(analyzer.calls, key=lambda call: call["range"]["start"]),
        # Every query runs in one transaction; it matters once there is more than one write.
        "transaction": writes > 1,
        "touched": [
            {"model": model, "fields": fields} for model, fields in analyzer.touched.items()
        ],
        "diagnostics": [*analyzer.errors, *analyzer.diagnostics],
        "errors": analyzer.errors,
        "pure": analyzer.pure and writes == 0,
    }


def analyze(input: Query):
    """`ClientAnalysis`: syntax and name errors come first among the diagnostics."""
    return {key: value for key, value in inspect(input.query).items() if key not in SERVER_ONLY}


def check(input: Query):
    """`ClientTypeDiagnostics`: what stops the query from running is an error, the rest a warning."""
    result = inspect(input.query)
    blocking = {(e["range"]["start"], e["message"]) for e in result["errors"]}
    return {
        "diagnostics": [
            {
                "message": diagnostic["message"],
                "severity": (
                    "error"
                    if (diagnostic["range"]["start"], diagnostic["message"]) in blocking
                    else "warning"
                ),
                "range": diagnostic["range"],
            }
            for diagnostic in result["diagnostics"]
        ]
    }
