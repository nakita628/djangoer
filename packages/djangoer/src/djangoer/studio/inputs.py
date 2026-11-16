"""What each operation takes: one frozen record, the same from the handler down to the domain.

Every function of a use case, of a service, and of the domain where a service enters it has a
single parameter, `input`, of one of these types (lint/studio.py holds them to it). A handler
builds the record from the request; nothing below takes it apart and passes the pieces on.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from .brands import Alias, ModelName, Offset, OrmQuery, Sql
from .contract.base import Cell, Row


class Input(BaseModel):
    """The base of every input: frozen, and strict about its fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class OnDatabase(Input):
    """An operation on one of the project's databases."""

    alias: Alias


class OnModel(OnDatabase):
    """An operation on the rows of one model."""

    model: Annotated[ModelName, Field(min_length=1)]


class ReadRows(OnModel):
    skip: Annotated[int, Field(ge=0)] = 0
    take: Annotated[int, Field(ge=1)] = 100
    search: str | None = None


class CreateRow(OnModel):
    values: Row


class UpdateRow(OnModel):
    where: Row
    values: Row


class DeleteRow(OnModel):
    where: Row


class RunSql(OnDatabase):
    sql: Sql
    params: list[Cell] = Field(default_factory=list)


class AnalyzeSql(OnDatabase):
    sql: Sql


class Query(Input):
    """A Django ORM query being read: analyzed, checked, formatted."""

    query: OrmQuery


class QueryAt(Query):
    """A query and a place in it: completed, hovered, its call explained."""

    offset: Annotated[Offset, Field(ge=0)]


class CompletionAt(QueryAt):
    """One item of the completions offered at a place."""

    name: Annotated[str, Field(min_length=1)]


class RunQuery(OnDatabase):
    """A query to run, or to preview the SQL of."""

    query: OrmQuery


class ExportFile(OnDatabase):
    """A file of the schema to hand over: `er.md`, `schema.dbml`, `er.svg`, `er.png`, `docs.md`."""

    name: str
    # The project's directory, which tells its own models from the ones of installed packages.
    root: Path


class WriteFile(Input):
    """A model file to write back, as it was edited in Studio."""

    path: str
    content: str
    # The project's directory, and the paths under it that may be written: the model files
    # Studio lists, and no other.
    root: Path
    files: tuple[str, ...]
