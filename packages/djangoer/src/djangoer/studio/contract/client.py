"""The Django ORM playground: a query read, completed, explained and run."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field

from ..brands import Offset, OrmQuery
from .base import Cell, Contract, TextRange

TypeSeverity = Literal["error", "warning", "info"]


class ClientStatus(Contract):
    available: bool
    source: str | None
    error: str | None
    typescript: str | None
    types_error: str | None


class ClientQueryBody(Contract):
    query: OrmQuery


class ClientRunBody(Contract):
    query: Annotated[OrmQuery, Field(min_length=1)]


class ClientPositionBody(Contract):
    query: OrmQuery
    offset: Annotated[Offset, Field(ge=0)]


class ClientCompletionDetailBody(Contract):
    query: OrmQuery
    offset: Annotated[Offset, Field(ge=0)]
    name: Annotated[str, Field(min_length=1)]


class ClientCompletionItem(Contract):
    label: str
    kind: str
    sort_text: str
    insert_text: str | None


class ClientCompletions(Contract):
    items: list[ClientCompletionItem]


class ClientCompletionDetail(Contract):
    detail: str | None
    documentation: str | None


class ClientHover(Contract):
    contents: str | None
    range: TextRange | None


class ClientSignatureParameter(Contract):
    label: str
    documentation: str | None


class ClientSignature(Contract):
    label: str
    documentation: str | None
    parameters: list[ClientSignatureParameter]


class ClientSignatureHelp(Contract):
    signatures: list[ClientSignature]
    active_signature: int
    active_parameter: int


class ClientFormatted(Contract):
    text: str


class ClientTypeDiagnostic(Contract):
    message: str
    severity: TypeSeverity
    range: TextRange


class ClientTypeDiagnostics(Contract):
    diagnostics: list[ClientTypeDiagnostic]


class ClientCall(Contract):
    model: str
    operation: str
    write: bool
    range: TextRange


class ClientDiagnostic(Contract):
    message: str
    range: TextRange


class ClientTouchedModel(Contract):
    model: str
    fields: list[str]


class ClientAnalysis(Contract):
    calls: list[ClientCall]
    transaction: bool
    touched: list[ClientTouchedModel]
    diagnostics: list[ClientDiagnostic]


class ClientSqlQuery(Contract):
    sql: str
    formatted: str
    params: list[Cell]
    duration_ms: float


class ClientResult(Contract):
    # The value the query gave, as JSON: rows for a queryset, a dict for an instance or an
    # aggregate, a number for a count.
    result: Any
    row_count: int | None
    truncated: bool
    queries: list[ClientSqlQuery]
    duration_ms: float


class ClientPreview(Contract):
    queries: list[ClientSqlQuery]
    duration_ms: float
