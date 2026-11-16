"""What a SQL statement reads and returns, worked out from its text alone.

A tokenizer and a clause reader, not a full parser: enough to draw a statement as a flow
(tables → JOIN → WHERE → GROUP BY → SELECT → ORDER BY → LIMIT), to mark the tables and columns it
touches on the ER diagram, and to type the rows it returns from the models behind the tables.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from django.apps import apps
from django.db import connections, models

from ..inputs import AnalyzeSql

KEYWORDS = frozenset(
    [
        "ABORT",
        "ACTION",
        "ADD",
        "AFTER",
        "ALL",
        "ALTER",
        "ANALYZE",
        "AND",
        "ANY",
        "AS",
        "ASC",
        "BEFORE",
        "BEGIN",
        "BETWEEN",
        "BY",
        "CASCADE",
        "CASE",
        "CAST",
        "CHECK",
        "COLLATE",
        "COLUMN",
        "COMMIT",
        "CONFLICT",
        "CONSTRAINT",
        "CREATE",
        "CROSS",
        "CURRENT",
        "CURRENT_DATE",
        "CURRENT_TIME",
        "CURRENT_TIMESTAMP",
        "DEFAULT",
        "DELETE",
        "DESC",
        "DISTINCT",
        "DO",
        "DROP",
        "ELSE",
        "END",
        "ESCAPE",
        "EXCEPT",
        "EXISTS",
        "EXPLAIN",
        "FALSE",
        "FETCH",
        "FILTER",
        "FIRST",
        "FOLLOWING",
        "FOR",
        "FOREIGN",
        "FROM",
        "FULL",
        "GLOB",
        "GROUP",
        "HAVING",
        "IF",
        "ILIKE",
        "IN",
        "INDEX",
        "INNER",
        "INSERT",
        "INTERSECT",
        "INTERVAL",
        "INTO",
        "IS",
        "ISNULL",
        "JOIN",
        "KEY",
        "LAST",
        "LATERAL",
        "LEFT",
        "LIKE",
        "LIMIT",
        "MATCH",
        "NATURAL",
        "NO",
        "NOT",
        "NOTHING",
        "NOTNULL",
        "NULL",
        "NULLS",
        "OF",
        "OFFSET",
        "ON",
        "ONLY",
        "OR",
        "ORDER",
        "OUTER",
        "OVER",
        "PARTITION",
        "PRAGMA",
        "PRECEDING",
        "PRIMARY",
        "RANGE",
        "RECURSIVE",
        "REFERENCES",
        "REGEXP",
        "RELEASE",
        "REPLACE",
        "RETURNING",
        "RIGHT",
        "ROLLBACK",
        "ROW",
        "ROWS",
        "SAVEPOINT",
        "SELECT",
        "SET",
        "SIMILAR",
        "SOME",
        "TABLE",
        "THEN",
        "TO",
        "TRANSACTION",
        "TRUE",
        "UNBOUNDED",
        "UNION",
        "UNIQUE",
        "UPDATE",
        "USING",
        "VACUUM",
        "VALUES",
        "VIEW",
        "WHEN",
        "WHERE",
        "WINDOW",
        "WITH",
        "WITHOUT",
    ]
)

JOIN_WORDS = frozenset({"JOIN", "INNER", "LEFT", "RIGHT", "FULL", "CROSS", "NATURAL", "OUTER"})
SET_OPERATORS = frozenset({"UNION", "INTERSECT", "EXCEPT"})

_TOKEN = re.compile(
    r"""
    (?P<space>\s+)
  | (?P<comment>--[^\n]*|/\*.*?\*/)
  | (?P<string>'(?:[^']|'')*')
  | (?P<ident>"(?:[^"]|"")*"|`[^`]*`|\[[^\]]*\])
  | (?P<param>\?|\$\d+|%s|%\(\w+\)s|(?<![:\w]):[A-Za-z_]\w*)
  | (?P<number>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)
  | (?P<word>[A-Za-z_][A-Za-z_0-9$]*)
  | (?P<op><>|!=|<=|>=|\|\||::|->>|->|[-+*/%=<>!~&|^])
  | (?P<punct>[(),.;])
    """,
    re.VERBOSE | re.DOTALL,
)


@dataclass
class Token:
    kind: str
    text: str
    start: int
    end: int
    depth: int = 0

    @property
    def upper(self) -> str:
        return self.text.upper() if self.kind == "word" else ""

    @property
    def name(self) -> str:
        """The identifier a word or a quoted name stands for."""
        if self.kind == "ident":
            return self.text[1:-1].replace('""', '"')
        return self.text

    def is_name(self) -> bool:
        return self.kind == "ident" or (self.kind == "word" and self.upper not in KEYWORDS)


def tokenize(sql: str) -> tuple[list[Token], list[dict[str, Any]]]:
    """The tokens of a script without spaces and comments, and what could not be read."""
    tokens: list[Token] = []
    problems: list[dict[str, Any]] = []
    position = 0
    depth = 0
    while position < len(sql):
        match = _TOKEN.match(sql, position)
        if match is None:
            char = sql[position]
            message = (
                "Unterminated string"
                if char == "'"
                else "Unterminated comment"
                if sql.startswith("/*", position)
                else f'Unexpected character "{char}"'
            )
            end = len(sql) if char in "'\"`" or sql.startswith("/*", position) else position + 1
            problems.append(
                {"severity": "error", "message": message, "range": {"start": position, "end": end}}
            )
            position = end
            continue
        kind = match.lastgroup or ""
        position = match.end()
        if kind in ("space", "comment"):
            continue
        text = match.group()
        if text == ")":
            depth = max(depth - 1, 0)
        tokens.append(Token(kind, text, match.start(), match.end(), depth))
        if text == "(":
            depth += 1
    return tokens, problems


def to_format_placeholders(sql: str) -> str:
    """A statement with `?` and `$1` placeholders as the `%s` Django's cursor takes."""
    out: list[str] = []
    position = 0
    while position < len(sql):
        match = _TOKEN.match(sql, position)
        if match is None:
            out.append(sql[position].replace("%", "%%"))
            position += 1
            continue
        text = match.group()
        kind = match.lastgroup
        if kind == "param" and (text == "?" or text.startswith("$")):
            out.append("%s")
        elif kind == "param":
            out.append(text)
        else:
            out.append(text.replace("%", "%%"))
        position = match.end()
    return "".join(out)


# ---------------------------------------------------------------------------
# The tables the models describe
# ---------------------------------------------------------------------------


def python_type(field_: models.Field | None) -> str:
    if field_ is None:
        return "Any"
    target = field_
    while target.is_relation and getattr(target, "target_field", None) is not None:
        target = target.target_field
    table = (
        (models.BooleanField, "bool"),
        (models.IntegerField, "int"),
        (models.FloatField, "float"),
        (models.DecimalField, "Decimal"),
        (models.DateTimeField, "datetime"),
        (models.DateField, "date"),
        (models.TimeField, "time"),
        (models.DurationField, "timedelta"),
        (models.UUIDField, "UUID"),
        (models.BinaryField, "bytes"),
        (models.JSONField, "Any"),
        (models.CharField, "str"),
        (models.TextField, "str"),
        (models.GenericIPAddressField, "str"),
        (models.FileField, "str"),
    )
    for cls, name in table:
        if isinstance(target, cls):
            return name
    return "Any"


@dataclass
class Column:
    name: str
    data_type: str | None = None
    py_type: str = "Any"
    nullable: bool | None = None
    sources: list[tuple[str, str]] = field(default_factory=list)


def catalog(alias: str = "default") -> dict[str, dict[str, Column]]:
    """Every table a model maps to, automatic many-to-many tables included, by lowercase name."""
    out: dict[str, dict[str, Column]] = {}
    for model in apps.get_models(include_auto_created=True):
        if model._meta.proxy or model._meta.swapped:
            continue
        columns: dict[str, Column] = {}
        for field_ in model._meta.concrete_fields:
            if field_.column is None:
                continue
            try:
                data_type = field_.db_type(connections[alias])
            except Exception:  # noqa: BLE001
                data_type = None
            columns[field_.column.lower()] = Column(
                field_.column,
                data_type,
                python_type(field_),
                bool(field_.null),
                [(model._meta.db_table, field_.column)],
            )
        out[model._meta.db_table.lower()] = columns
    return out


# ---------------------------------------------------------------------------
# One statement
# ---------------------------------------------------------------------------


@dataclass
class Source:
    """Something a FROM clause names: a table, a CTE, a subquery or a function."""

    node: str
    name: str
    alias: str | None
    columns: dict[str, Column] | None
    table: dict[str, Any] | None = None

    @property
    def key(self) -> str:
        return (self.alias or self.name).lower()


@dataclass
class Scope:
    name: str
    sources: list[Source] = field(default_factory=list)
    parent: Scope | None = None

    def find(self, qualifier: str) -> Source | None:
        scope: Scope | None = self
        while scope is not None:
            for source in scope.sources:
                if source.key == qualifier.lower() or source.name.lower() == qualifier.lower():
                    return source
            scope = scope.parent
        return None


class Statement:
    def __init__(self, sql: str, tokens: list[Token], tables: dict[str, dict[str, Column]]):
        self.sql = sql
        self.tokens = tokens
        self.catalog = tables
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []
        self.tables: list[dict[str, Any]] = []
        self.diagnostics: list[dict[str, Any]] = []
        self.ctes: dict[str, tuple[str, list[Column]]] = {}
        self.resolved: dict[int, Column] = {}
        self.output: list[dict[str, Any]] = []
        self.subqueries = 0

    # -- graph ---------------------------------------------------------------

    def node(
        self, kind: str, label: str, details: list[str], tokens: list[Token], scope: str
    ) -> str:
        node_id = f"n{len(self.nodes) + 1}"
        self.nodes.append(
            {
                "id": node_id,
                "kind": kind,
                "label": label,
                "details": details,
                "range": {"start": tokens[0].start, "end": tokens[-1].end} if tokens else None,
                "scope": scope,
                "columns": [],
            }
        )
        return node_id

    def edge(self, source: str | None, target: str | None, kind: str = "flow", label=None) -> None:
        if source is None or target is None:
            return
        self.edges.append(
            {
                "id": f"e{len(self.edges) + 1}",
                "source": source,
                "target": target,
                "label": label,
                "kind": kind,
            }
        )

    def text(self, tokens: list[Token]) -> str:
        if not tokens:
            return ""
        return " ".join(self.sql[tokens[0].start : tokens[-1].end].split())

    def warn(self, message: str, token: Token) -> None:
        self.diagnostics.append(
            {
                "severity": "warning",
                "message": message,
                "range": {"start": token.start, "end": token.end},
            }
        )

    # -- reading -------------------------------------------------------------

    def query(self, tokens: list[Token], scope: Scope) -> tuple[str | None, list[Column]]:
        """A whole query: its CTEs, then its SELECTs joined by set operators."""
        tokens = self.strip_parentheses(tokens)
        if not tokens:
            return None, []
        base = tokens[0].depth
        if tokens[0].upper == "WITH":
            tokens = self.with_clause(tokens, scope)
            if not tokens:
                return None, []
        parts: list[list[Token]] = [[]]
        operators: list[str] = []
        for token in tokens:
            if token.depth == base and token.upper in SET_OPERATORS:
                operators.append(token.upper)
                parts.append([])
            elif token.depth == base and token.upper == "ALL" and operators and not parts[-1]:
                operators[-1] += " ALL"
            else:
                parts[-1].append(token)
        results = [self.statement(part, scope) for part in parts if part]
        if len(results) == 1:
            return results[0]
        union = self.node("union", operators[0], operators[1:], tokens, scope.name)
        for node_id, _columns in results:
            self.edge(node_id, union)
        return union, results[0][1] if results else []

    def strip_parentheses(self, tokens: list[Token]) -> list[Token]:
        while (
            len(tokens) >= 2
            and tokens[0].text == "("
            and tokens[-1].text == ")"
            and all(token.depth > tokens[0].depth for token in tokens[1:-1])
        ):
            tokens = tokens[1:-1]
        return tokens

    def group_end(self, tokens: list[Token], start: int) -> int:
        """The index of the `)` closing the `(` at `start`, or the last index."""
        depth = tokens[start].depth
        for index in range(start + 1, len(tokens)):
            if tokens[index].text == ")" and tokens[index].depth == depth:
                return index
        return len(tokens) - 1

    def with_clause(self, tokens: list[Token], scope: Scope) -> list[Token]:
        index = 1
        if index < len(tokens) and tokens[index].upper == "RECURSIVE":
            index += 1
        while index < len(tokens) and tokens[index].is_name():
            name = tokens[index]
            index += 1
            if index < len(tokens) and tokens[index].text == "(":
                index = self.group_end(tokens, index) + 1
            if index < len(tokens) and tokens[index].upper == "AS":
                index += 1
            while index < len(tokens) and tokens[index].upper in ("NOT", "MATERIALIZED"):
                index += 1
            if index >= len(tokens) or tokens[index].text != "(":
                break
            end = self.group_end(tokens, index)
            # Registered before its body is read, so a recursive CTE can name itself.
            node_id = self.node("cte", name.name, [], tokens[index : end + 1], name.name)
            self.ctes[name.name.lower()] = (node_id, [])
            inner, columns = self.query(tokens[index + 1 : end], Scope(name.name, parent=scope))
            self.edge(inner, node_id)
            self.ctes[name.name.lower()] = (node_id, columns)
            index = end + 1
            if index < len(tokens) and tokens[index].text == ",":
                index += 1
                continue
            break
        return tokens[index:]

    def clauses(self, tokens: list[Token], starts: dict[str, str]) -> dict[str, list[Token]]:
        """The tokens of each clause, split at the keywords that open one at this depth."""
        base = tokens[0].depth
        out: dict[str, list[Token]] = {}
        current: str | None = None
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token.depth == base and token.upper in starts:
                current = starts[token.upper]
                out.setdefault(current, [])
                if (
                    token.upper in ("GROUP", "ORDER")
                    and index + 1 < len(tokens)
                    and tokens[index + 1].upper == "BY"
                ):
                    index += 1
            elif current is not None:
                out[current].append(token)
            index += 1
        return out

    def statement(self, tokens: list[Token], scope: Scope) -> tuple[str | None, list[Column]]:
        tokens = self.strip_parentheses(tokens)
        if not tokens:
            return None, []
        verb = tokens[0].upper
        if verb == "SELECT":
            return self.select(tokens, scope)
        if verb == "VALUES":
            return self.node("values", "VALUES", [self.text(tokens[1:])], tokens, scope.name), []
        if verb in ("INSERT", "REPLACE"):
            return self.insert(tokens, scope)
        if verb == "UPDATE":
            return self.update(tokens, scope)
        if verb == "DELETE":
            return self.delete(tokens, scope)
        return None, []

    # -- FROM ----------------------------------------------------------------

    def table(self, name_tokens: list[Token], alias: str | None, scope: Scope) -> Source:
        name = name_tokens[-1].name
        cte = self.ctes.get(name.lower()) if len(name_tokens) == 1 else None
        if cte is not None:
            node_id, columns = cte
            source = Source(
                node_id, name, alias, {column.name.lower(): column for column in columns}
            )
            scope.sources.append(source)
            return source
        columns = self.catalog.get(name.lower())
        node_id = self.node(
            "table", name, [f"AS {alias}"] if alias else [], name_tokens, scope.name
        )
        ref = {
            "nodeId": node_id,
            "name": name,
            "alias": alias,
            "scope": scope.name,
            "known": columns is not None,
            "columnsUsed": [],
            "range": {"start": name_tokens[0].start, "end": name_tokens[-1].end},
        }
        self.tables.append(ref)
        if columns is None:
            self.warn(f'Unknown table "{name}"', name_tokens[-1])
        source = Source(node_id, name, alias, columns, ref)
        scope.sources.append(source)
        return source

    def alias(self, tokens: list[Token], index: int) -> tuple[str | None, int]:
        if index < len(tokens) and tokens[index].upper == "AS":
            index += 1
        if index < len(tokens) and tokens[index].is_name():
            return tokens[index].name, index + 1
        return None, index

    def from_clause(self, tokens: list[Token], scope: Scope) -> tuple[list[Source], list[str]]:
        """The sources a FROM clause lists, and the conditions they are joined on."""
        if not tokens:
            return [], []
        base = tokens[0].depth
        sources: list[Source] = []
        conditions: list[str] = []
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token.depth != base:
                index += 1
                continue
            if token.text == "," or token.upper in JOIN_WORDS or token.upper == "LATERAL":
                index += 1
                continue
            if token.upper in ("ON", "USING"):
                end = index + 1
                while end < len(tokens) and not (
                    tokens[end].depth == base
                    and (tokens[end].text == "," or tokens[end].upper in JOIN_WORDS)
                ):
                    end += 1
                condition = tokens[index + 1 : end]
                conditions.append(f"{token.upper} {self.text(condition)}")
                self.nested(condition, scope, None)
                index = end
                continue
            if token.text == "(":
                end = self.group_end(tokens, index)
                alias, after = self.alias(tokens, end + 1)
                self.subqueries += 1
                name = alias or f"subquery {self.subqueries}"
                inner, columns = self.query(tokens[index + 1 : end], Scope(name, parent=scope))
                node_id = self.node("subquery", name, [], tokens[index : end + 1], scope.name)
                self.edge(inner, node_id)
                source = Source(node_id, name, alias, {c.name.lower(): c for c in columns})
                scope.sources.append(source)
                sources.append(source)
                index = after
                continue
            if token.is_name():
                parts = [token]
                index += 1
                while (
                    index + 1 < len(tokens)
                    and tokens[index].text == "."
                    and tokens[index + 1].is_name()
                ):
                    parts.append(tokens[index + 1])
                    index += 2
                if index < len(tokens) and tokens[index].text == "(":
                    end = self.group_end(tokens, index)
                    alias, after = self.alias(tokens, end + 1)
                    node_id = self.node(
                        "function", parts[-1].name, [], tokens[index - 1 : end + 1], scope.name
                    )
                    source = Source(node_id, parts[-1].name, alias, None)
                    scope.sources.append(source)
                    sources.append(source)
                    index = after
                    continue
                alias, index = self.alias(tokens, index)
                sources.append(self.table(parts, alias, scope))
                continue
            index += 1
        return sources, conditions

    # -- columns -------------------------------------------------------------

    def use(self, source: Source, column: Column) -> None:
        if source.table is not None and column.name not in source.table["columnsUsed"]:
            source.table["columnsUsed"].append(column.name)

    def lookup(self, name: str, scope: Scope, token: Token) -> Column | None:
        """The column a bare name means, if exactly one source in reach has it."""
        current: Scope | None = scope
        while current is not None:
            found = [
                (source, source.columns[name.lower()])
                for source in current.sources
                if source.columns is not None and name.lower() in source.columns
            ]
            if found:
                source, column = found[0]
                self.use(source, column)
                return column
            current = current.parent
        every_known = scope.sources and all(source.columns is not None for source in scope.sources)
        if every_known and scope.parent is None:
            self.warn(f'Unknown column "{name}"', token)
        return None

    def references(self, tokens: list[Token], scope: Scope, skip: set[str] | None = None) -> None:
        """Mark every column the tokens name on the table it belongs to."""
        skip = skip or set()
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if not token.is_name():
                index += 1
                continue
            previous = tokens[index - 1] if index else None
            following = tokens[index + 1] if index + 1 < len(tokens) else None
            if previous is not None and (previous.text == "." or previous.upper == "AS"):
                index += 1
                continue
            if following is not None and following.text == "(":
                index += 1
                continue
            if following is not None and following.text == "." and index + 2 < len(tokens):
                member = tokens[index + 2]
                source = scope.find(token.name)
                if source is not None and source.columns is not None:
                    if member.text == "*":
                        for column in source.columns.values():
                            self.use(source, column)
                    elif member.is_name():
                        column = source.columns.get(member.name.lower())
                        if column is not None:
                            self.use(source, column)
                            self.resolved[id(member)] = column
                        else:
                            self.warn(f'Unknown column "{member.name}"', member)
                index += 3
                continue
            if token.name.lower() not in skip:
                column = self.lookup(token.name, scope, token)
                if column is not None:
                    self.resolved[id(token)] = column
            index += 1

    def nested(
        self,
        tokens: list[Token],
        scope: Scope,
        target: str | None,
        *,
        skip: set[str] | None = None,
        refs: bool = True,
    ) -> list[Token]:
        """Read the subqueries inside an expression; the tokens that are left are its own.

        `skip` names what is not a column here (the aliases of the select list); with `refs` off
        the caller marks the columns itself.
        """
        own: list[Token] = []
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if (
                token.text == "("
                and index + 1 < len(tokens)
                and tokens[index + 1].upper in ("SELECT", "WITH")
            ):
                end = self.group_end(tokens, index)
                self.subqueries += 1
                name = f"subquery {self.subqueries}"
                inner, _columns = self.query(tokens[index + 1 : end], Scope(name, parent=scope))
                node_id = self.node("subquery", name, [], tokens[index : end + 1], scope.name)
                self.edge(inner, node_id)
                self.edge(node_id, target, "lookup")
                index = end + 1
                continue
            own.append(token)
            index += 1
        if refs:
            self.references(own, scope, skip)
        return own

    def split_alias(self, item: list[Token]) -> tuple[str | None, list[Token]]:
        """`expression AS name` or `expression name`: the name, and the expression alone."""
        if len(item) >= 3 and item[-2].upper == "AS" and item[-1].is_name():
            return item[-1].name, item[:-2]
        if (
            len(item) >= 2
            and item[-1].is_name()
            and item[-2].text != "."
            and (
                item[-2].is_name()
                or item[-2].text == ")"
                or item[-2].kind in ("number", "string")
                or item[-2].upper == "END"
            )
        ):
            return item[-1].name, item[:-1]
        return None, item

    def items(self, tokens: list[Token]) -> list[list[Token]]:
        """A list split at the commas of its own depth."""
        if not tokens:
            return []
        base = tokens[0].depth
        out: list[list[Token]] = [[]]
        for token in tokens:
            if token.text == "," and token.depth == base:
                out.append([])
            else:
                out[-1].append(token)
        return [item for item in out if item]

    def projection(self, tokens: list[Token], scope: Scope) -> list[tuple[Column, str]]:
        """The columns a select list (or RETURNING) gives with the expression of each, `*` spread
        over the sources."""
        out: list[tuple[Column, str]] = []
        for item in self.items(tokens):
            if item[-1].text == "*":
                qualifier = item[0].name if len(item) == 3 else None
                prefix = f"{qualifier}." if qualifier else ""
                for source in scope.sources:
                    if qualifier is not None and source is not scope.find(qualifier):
                        continue
                    for column in (source.columns or {}).values():
                        self.use(source, column)
                        out.append((column, f"{prefix}{column.name}"))
                continue
            name, expression = self.split_alias(item)
            plain = all(token.is_name() or token.text == "." for token in expression)
            column = self.resolved.get(id(expression[-1])) if plain else None
            if name is None:
                name = expression[-1].name if plain else self.text(expression)
            out.append(
                (
                    Column(
                        name,
                        column.data_type if column else None,
                        column.py_type if column else self.infer(expression),
                        column.nullable if column else None,
                        column.sources if column else [],
                    ),
                    self.text(expression),
                )
            )
        return out

    def infer(self, expression: list[Token]) -> str:
        """The type of what is plainly a count, a number or a string."""
        head = expression[0]
        if head.upper == "COUNT":
            return "int"
        if len(expression) == 1 and head.kind == "number":
            return "float" if "." in head.text else "int"
        if len(expression) == 1 and head.kind == "string":
            return "str"
        if head.upper in ("MIN", "MAX") and len(expression) >= 4:
            inner = self.resolved.get(id(expression[-2]))
            if inner is not None:
                return inner.py_type
        return "Any"

    # -- statements ----------------------------------------------------------

    def select(self, tokens: list[Token], scope: Scope) -> tuple[str | None, list[Column]]:
        starts = {
            "SELECT": "select",
            "FROM": "from",
            "WHERE": "where",
            "GROUP": "group",
            "HAVING": "having",
            "WINDOW": "window",
            "ORDER": "order",
            "LIMIT": "limit",
            "OFFSET": "limit",
            "FETCH": "limit",
        }
        clauses = self.clauses(tokens, starts)
        scope_name = scope.name
        sources, conditions = self.from_clause(clauses.get("from", []), scope)
        current: str | None = sources[0].node if sources else None
        if len(sources) > 1:
            join = self.node("join", "JOIN", conditions, clauses["from"], scope_name)
            for source in sources:
                self.edge(source.node, join)
            current = join

        select_list = clauses.get("select", [])
        distinct = bool(select_list) and select_list[0].upper == "DISTINCT"
        if distinct or (select_list and select_list[0].upper == "ALL"):
            select_list = select_list[1:]
        # Names the select list makes up: GROUP BY, HAVING and ORDER BY may use them.
        aliases = {
            name.lower()
            for name, _expression in map(self.split_alias, self.items(select_list))
            if name is not None
        }

        def step(kind: str, label: str, clause: str, own: bool = True, skip=None) -> None:
            nonlocal current
            body = clauses.get(clause)
            if not body:
                return
            node_id = self.node(kind, label, [self.text(body)], body, scope_name)
            if own:
                self.nested(body, scope, node_id, skip=skip)
            self.edge(current, node_id)
            current = node_id

        step("filter", "WHERE", "where")
        step("aggregate", "GROUP BY", "group", skip=aliases)
        step("having", "HAVING", "having", skip=aliases)

        project = self.node(
            "project",
            "SELECT",
            [self.text(item) for item in self.items(select_list)],
            select_list,
            scope_name,
        )
        own = self.nested(select_list, scope, project, refs=False)
        for item in self.items(own):
            self.references(self.split_alias(item)[1], scope)
        pairs = self.projection(own, scope)
        columns = [column for column, _expression in pairs]
        if scope.parent is None and not self.output:
            self.output = [
                {"column": column, "expression": expression} for column, expression in pairs
            ]
        self.edge(current, project)
        current = project
        if distinct:
            node_id = self.node("distinct", "DISTINCT", [], select_list[:1], scope_name)
            self.edge(current, node_id)
            current = node_id
        step("sort", "ORDER BY", "order", skip=aliases)
        step("limit", "LIMIT", "limit", own=False)
        return current, columns

    def target(self, tokens: list[Token], index: int, scope: Scope) -> tuple[Source | None, int]:
        """The table a write names, with its alias."""
        if index < len(tokens) and tokens[index].upper == "ONLY":
            index += 1
        parts: list[Token] = []
        while index < len(tokens) and tokens[index].is_name():
            parts.append(tokens[index])
            index += 1
            if index < len(tokens) and tokens[index].text == ".":
                index += 1
                continue
            break
        if not parts:
            return None, index
        alias = None
        if index < len(tokens) and (
            tokens[index].upper == "AS"
            or (tokens[index].is_name() and tokens[index].depth == parts[0].depth)
        ):
            alias, index = self.alias(tokens, index)
        return self.table(parts, alias, scope), index

    def returning(self, body: list[Token] | None, current: str | None, scope: Scope):
        if not body:
            return current, []
        node_id = self.node("returning", "RETURNING", [self.text(body)], body, scope.name)
        for item in self.items(body):
            self.references(self.split_alias(item)[1], scope)
        pairs = self.projection(body, scope)
        columns = [column for column, _expression in pairs]
        if scope.parent is None:
            self.output = [
                {"column": column, "expression": expression} for column, expression in pairs
            ]
        self.edge(current, node_id)
        return node_id, columns

    def insert(self, tokens: list[Token], scope: Scope) -> tuple[str | None, list[Column]]:
        index = 1
        while index < len(tokens) and tokens[index].upper in (
            "OR",
            "REPLACE",
            "IGNORE",
            "ABORT",
            "INTO",
        ):
            index += 1
        source, index = self.target(tokens, index, scope)
        named: list[Token] = []
        if index < len(tokens) and tokens[index].text == "(":
            end = self.group_end(tokens, index)
            named = [token for token in tokens[index + 1 : end] if token.is_name()]
            index = end + 1
        columns_named: list[Column | None] = []
        if source is not None and source.columns is not None:
            for token in named:
                column = source.columns.get(token.name.lower())
                if column is None:
                    self.warn(f'Unknown column "{token.name}"', token)
                else:
                    self.use(source, column)
                columns_named.append(column)
        rest = tokens[index:]
        clauses = self.clauses(rest, {"RETURNING": "returning"}) if rest else {}
        returning = clauses.get("returning")
        body = rest[: len(rest) - len(returning) - 1] if returning else rest
        feed: str | None = None
        if body and body[0].upper == "VALUES":
            feed = self.node("values", "VALUES", [self.text(body[1:])], body, scope.name)
            first = (
                body[1 : self.group_end(body, 1) + 1]
                if len(body) > 1 and body[1].text == "("
                else []
            )
            for position, item in enumerate(self.items(first[1:-1])):
                if len(item) == 1 and item[0].kind == "param" and position < len(columns_named):
                    column = columns_named[position]
                    if column is not None:
                        self.resolved[id(item[0])] = column
        elif (body and body[0].upper in ("SELECT", "WITH")) or (body and body[0].text == "("):
            feed, _columns = self.query(body, Scope("insert source", parent=None))
        node_id = self.node(
            "insert",
            "INSERT",
            [token.name for token in named],
            tokens[:index] or tokens[:1],
            scope.name,
        )
        self.edge(feed, node_id)
        self.edge(node_id, source.node if source else None)
        return self.returning(returning, node_id, scope)

    def update(self, tokens: list[Token], scope: Scope) -> tuple[str | None, list[Column]]:
        index = 1
        while index < len(tokens) and tokens[index].upper in ("OR", "REPLACE", "IGNORE", "ABORT"):
            index += 1
        source, index = self.target(tokens, index, scope)
        clauses = (
            self.clauses(
                tokens[index:],
                {"SET": "set", "FROM": "from", "WHERE": "where", "RETURNING": "returning"},
            )
            if index < len(tokens)
            else {}
        )
        extra, _conditions = self.from_clause(clauses.get("from", []), scope)
        current = source.node if source else None
        for other in extra:
            self.edge(other.node, current)
        where = clauses.get("where")
        if where:
            node_id = self.node("filter", "WHERE", [self.text(where)], where, scope.name)
            self.nested(where, scope, node_id)
            self.edge(current, node_id)
            current = node_id
        assignments = clauses.get("set", [])
        node_id = self.node(
            "update",
            "UPDATE",
            [self.text(item) for item in self.items(assignments)],
            assignments or tokens[:1],
            scope.name,
        )
        own = self.nested(assignments, scope, node_id)
        for item in self.items(own):
            # `column = ?`: the parameter is of the column's type.
            if len(item) == 3 and item[1].text == "=" and item[2].kind == "param":
                column = self.resolved.get(id(item[0]))
                if column is not None:
                    self.resolved[id(item[2])] = column
        self.edge(current, node_id)
        return self.returning(clauses.get("returning"), node_id, scope)

    def delete(self, tokens: list[Token], scope: Scope) -> tuple[str | None, list[Column]]:
        index = 1
        if index < len(tokens) and tokens[index].upper == "FROM":
            index += 1
        source, index = self.target(tokens, index, scope)
        clauses = (
            self.clauses(
                tokens[index:], {"USING": "from", "WHERE": "where", "RETURNING": "returning"}
            )
            if index < len(tokens)
            else {}
        )
        self.from_clause(clauses.get("from", []), scope)
        current = source.node if source else None
        where = clauses.get("where")
        if where:
            node_id = self.node("filter", "WHERE", [self.text(where)], where, scope.name)
            self.nested(where, scope, node_id)
            self.edge(current, node_id)
            current = node_id
        node_id = self.node("delete", "DELETE", [], tokens[:1], scope.name)
        self.edge(current, node_id)
        return self.returning(clauses.get("returning"), node_id, scope)

    # -- results -------------------------------------------------------------

    def parameters(self) -> list[dict[str, Any]]:
        out = []
        comparisons = {"=", "<", ">", "<=", ">=", "<>", "!="}
        for index, token in enumerate(self.tokens):
            if token.kind != "param":
                continue
            column = self.resolved.get(id(token))
            start = index
            if index >= 2 and (
                self.tokens[index - 1].text in comparisons
                or self.tokens[index - 1].upper in ("LIKE", "ILIKE")
            ):
                # `u.id = ?`: back over the column the placeholder is compared with.
                start = index - 2
                column = column or self.resolved.get(id(self.tokens[index - 2]))
                while start >= 2 and self.tokens[start - 1].text == ".":
                    start -= 2
            out.append(
                {
                    "index": len(out) + 1,
                    "placeholder": token.text,
                    "dataType": column.data_type if column else None,
                    "tsType": column.py_type if column else "Any",
                    "nullable": column.nullable if column else None,
                    "context": self.text(self.tokens[start : index + 1]),
                }
            )
        return out

    def fill_columns(self) -> None:
        """Every column of a known table on its node, the ones the statement names marked."""
        by_node = {ref["nodeId"]: ref for ref in self.tables}
        for node in self.nodes:
            ref = by_node.get(node["id"])
            if ref is None or not ref["known"]:
                continue
            used = set(ref["columnsUsed"])
            node["columns"] = [
                {"name": column.name, "dataType": column.data_type, "used": column.name in used}
                for column in self.catalog[ref["name"].lower()].values()
            ]


def _kind(tokens: list[Token]) -> str:
    base = tokens[0].depth
    for token in tokens:
        if token.depth != base:
            continue
        verb = token.upper
        if verb in ("SELECT", "VALUES"):
            return "select"
        if verb in ("INSERT", "REPLACE"):
            return "insert"
        if verb == "UPDATE":
            return "update"
        if verb == "DELETE":
            return "delete"
        if verb != "WITH" and tokens[0].upper != "WITH":
            return "other"
    return "other"


def _identifier(name: str) -> str:
    cleaned = re.sub(r"\W", "_", name)
    return cleaned if cleaned.isidentifier() else f"_{cleaned}"


def _row_type(output: list[dict[str, Any]]) -> str:
    if not output:
        return "Row = None"
    names_ = [entry["column"].name for entry in output]
    if all(name.isidentifier() for name in names_) and len(set(names_)) == len(names_):
        lines = ["class Row(TypedDict):"]
        for entry in output:
            column: Column = entry["column"]
            optional = " | None" if column.nullable and column.py_type != "Any" else ""
            lines.append(f"    {column.name}: {column.py_type}{optional}")
        return "\n".join(lines)
    # A column named by an expression cannot be a class attribute: the functional form takes any key.
    body = ", ".join(
        f"{entry['column'].name!r}: {entry['column'].py_type}"
        + (" | None" if entry["column"].nullable and entry["column"].py_type != "Any" else "")
        for entry in output
    )
    return f'Row = TypedDict("Row", {{{body}}})'


def _params_type(parameters: list[dict[str, Any]]) -> str:
    if not parameters:
        return "Params = tuple[()]"
    parts = [
        parameter["tsType"]
        + (" | None" if parameter["nullable"] and parameter["tsType"] != "Any" else "")
        for parameter in parameters
    ]
    return f"Params = tuple[{', '.join(parts)}]"


def analyze_statement(
    sql: str, tokens: list[Token], tables: dict[str, dict[str, Column]], problems: list[dict]
) -> dict[str, Any]:
    start, end = tokens[0].start, tokens[-1].end
    own_problems = [
        problem for problem in problems if start <= problem["range"]["start"] <= end + 1
    ]
    balance = sum(1 if t.text == "(" else -1 if t.text == ")" else 0 for t in tokens)
    if balance != 0:
        own_problems.append(
            {
                "severity": "error",
                "message": "Unbalanced parentheses",
                "range": {"start": start, "end": end},
            }
        )
    statement = Statement(sql, tokens, tables)
    kind = "invalid" if own_problems else _kind(tokens)
    if kind not in ("invalid", "other"):
        try:
            statement.query(tokens, Scope("main"))
        except (IndexError, KeyError, RecursionError):
            # A statement cut short mid-clause while it is being typed: what was read stands.
            pass
    statement.fill_columns()
    parameters = statement.parameters()
    columns = [
        {
            "name": entry["column"].name,
            "expression": entry["expression"] or entry["column"].name,
            "dataType": entry["column"].data_type,
            "tsType": entry["column"].py_type,
            "nullable": entry["column"].nullable,
            "sources": [
                {"table": table, "column": column} for table, column in entry["column"].sources
            ],
        }
        for entry in statement.output
    ]
    return {
        "kind": kind,
        "text": sql[start:end],
        "range": {"start": start, "end": end},
        "nodes": statement.nodes,
        "edges": statement.edges,
        "tables": statement.tables,
        "columns": columns,
        "parameters": parameters,
        "diagnostics": own_problems + statement.diagnostics,
        "rowType": _row_type(statement.output),
        "paramsType": _params_type(parameters),
    }


def analyze(input: AnalyzeSql):
    sql, alias = input.sql, input.alias
    tokens, problems = tokenize(sql)
    tables = catalog(alias)
    statements: list[list[Token]] = [[]]
    for token in tokens:
        if token.text == ";" and token.depth == 0:
            statements.append([])
        else:
            statements[-1].append(token)
    return {
        "statements": [
            analyze_statement(sql, statement, tables, problems)
            for statement in statements
            if statement
        ]
    }
