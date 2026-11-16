"""The database: its status, the rows of a model, SQL and what a statement reads."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from ..brands import Sql
from .base import Cell, Contract, NonNegativeInt, Row, TextRange

Dialect = Literal["postgresql", "mysql", "sqlite"]
StatementKind = Literal["select", "insert", "update", "delete", "other", "invalid"]
NodeKind = Literal[
    "table",
    "cte",
    "subquery",
    "values",
    "function",
    "join",
    "filter",
    "aggregate",
    "having",
    "project",
    "distinct",
    "sort",
    "limit",
    "union",
    "insert",
    "update",
    "delete",
    "returning",
]
EdgeKind = Literal["flow", "lookup"]
SqlSeverity = Literal["error", "warning", "info"]

MAX_TAKE = 1000
Skip = Annotated[int, Field(ge=0)]
Take = Annotated[int, Field(ge=1, le=MAX_TAKE)]


class RowsQuery(Contract):
    """The page of rows asked for, and what they are searched by."""

    skip: Skip = 0
    take: Take = 100
    search: str | None = None


class DbStatus(Contract):
    connected: bool
    dialect: Dialect | None
    url: str | None
    source: Literal["settings"] | None
    error: str | None


class Counts(Contract):
    counts: dict[str, int]


class Rows(Contract):
    rows: list[Row]
    total: int
    skip: int
    take: int
    key: list[str]
    columns: list[str]


class InsertBody(Contract):
    values: Row


class UpdateBody(Contract):
    where: Row
    values: Row


class DeleteBody(Contract):
    where: Row


class Affected(Contract):
    affected: int


class SqlBody(Contract):
    sql: Annotated[Sql, Field(min_length=1)]
    params: list[Cell] = Field(default_factory=list)


class SqlResult(Contract):
    columns: list[str]
    rows: list[Row]
    row_count: int
    duration_ms: float


class AnalyzeBody(Contract):
    sql: Sql


class NodeColumn(Contract):
    name: str
    data_type: str | None
    used: bool


class GraphNode(Contract):
    id: str
    kind: NodeKind
    label: str
    details: list[str]
    range: TextRange | None
    scope: str
    columns: list[NodeColumn]


class GraphEdge(Contract):
    id: str
    source: str
    target: str
    label: str | None
    kind: EdgeKind


class ColumnSource(Contract):
    table: str
    column: str


class OutputColumn(Contract):
    name: str
    expression: str
    data_type: str | None
    # A Python type here (`int`, `datetime`): the key keeps the name the client reads.
    ts_type: str
    nullable: bool | None
    sources: list[ColumnSource]


class TableRef(Contract):
    node_id: str
    name: str
    alias: str | None
    scope: str
    known: bool
    columns_used: list[str]
    range: TextRange


class SqlParameter(Contract):
    index: NonNegativeInt
    placeholder: str
    data_type: str | None
    ts_type: str
    nullable: bool | None
    context: str


class SqlDiagnostic(Contract):
    severity: SqlSeverity
    message: str
    range: TextRange | None


class StatementAnalysis(Contract):
    kind: StatementKind
    text: str
    range: TextRange
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    tables: list[TableRef]
    columns: list[OutputColumn]
    parameters: list[SqlParameter]
    diagnostics: list[SqlDiagnostic]
    row_type: str
    params_type: str


class Analysis(Contract):
    statements: list[StatementAnalysis]


class PlanNode(Contract):
    id: str
    parent: str | None
    label: str
    detail: str | None
    cost: float | None
    rows: float | None


class Plan(Contract):
    dialect: Dialect
    nodes: list[PlanNode]
    raw: str
