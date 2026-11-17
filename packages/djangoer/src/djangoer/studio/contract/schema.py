"""The schema Studio draws: Django models as models, fields, enums and relations."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field as PydanticField

from ..brands import Offset
from .base import Contract

FieldKind = Literal["scalar", "object", "enum", "unsupported"]
IndexType = Literal["id", "unique", "normal", "fulltext"]
Cardinality = Literal["zero-one", "one", "zero-many", "many"]
RelationOrigin = Literal["inferred", "annotated", "implicit-many-to-many", "generic"]
Severity = Literal["error", "warning", "information", "hint"]


class SchemaFile(Contract):
    """A module that declares models, as Studio names and shows it."""

    path: str
    content: str


class FileWrite(Contract):
    """A model file as it was edited in Studio, to write back."""

    path: str
    content: str


class SourceBody(Contract):
    """A model file as it is being edited."""

    path: str
    content: str


class SourcePositionBody(SourceBody):
    """A place in a model file being edited."""

    offset: Annotated[Offset, PydanticField(ge=0)]


class Location(Contract):
    file: str
    line: int


class FieldRelation(Contract):
    """The relation an object field follows: `author` reads `author_id` → `Author.id`."""

    name: str | None
    from_fields: list[str]
    to_fields: list[str]
    on_delete: str | None
    on_update: str | None


class Field(Contract):
    name: str
    db_name: str | None
    kind: FieldKind
    type: str
    is_list: bool
    is_required: bool
    is_id: bool
    is_unique: bool
    is_updated_at: bool
    is_foreign_key: bool
    default: str | None
    native_type: str | None
    documentation: str | None
    annotations: list[str]
    relation: FieldRelation | None
    attributes: list[str]


class Index(Contract):
    type: IndexType
    name: str | None
    db_name: str | None
    fields: list[str]
    # What an index on expressions indexes beside its fields, as SQL: `LOWER("email")`.
    expressions: list[str]
    # The `WHERE` of a partial index, as SQL: `"primary" = 1`.
    condition: str | None
    # The operator class of each column, where one is named: `varchar_pattern_ops`.
    opclasses: list[str]
    attribute: str


class GenericForeignKey(Contract):
    """A pair of columns that names a row of any model: `content_object` is the row whose
    content type is in `content_type_id` and whose key is in `object_id`."""

    name: str
    content_type_field: str
    object_id_field: str


class Model(Contract):
    name: str
    app: str
    db_name: str | None
    documentation: str | None
    annotations: list[str]
    fields: list[Field]
    primary_key: list[str] | None
    indexes: list[Index]
    generic_foreign_keys: list[GenericForeignKey]
    attributes: list[str]
    location: Location | None


class EnumValue(Contract):
    name: str
    db_name: str | None


class Enum(Contract):
    name: str
    db_name: str | None
    documentation: str | None
    values: list[EnumValue]
    location: Location | None


class RelationEnd(Contract):
    model: str
    field: str
    cardinality: Cardinality


class Through(Contract):
    """The table Django creates for a many-to-many: its columns, the two that refer to each
    side, and its indexes."""

    db_name: str
    from_column: str
    to_column: str
    fields: list[Field]
    indexes: list[Index]


class Relation(Contract):
    id: str
    name: str | None
    origin: RelationOrigin
    # `from` is a keyword, so the attribute carries an underscore the wire does not.
    from_: RelationEnd = PydanticField(alias="from")
    to: RelationEnd
    on_delete: str | None
    on_update: str | None
    # The table that joins the two, for a many-to-many with no through model of its own.
    through: Through | None


class Schema(Contract):
    files: list[SchemaFile]
    provider: str | None
    models: list[Model]
    enums: list[Enum]
    relations: list[Relation]


class LspPosition(Contract):
    line: int
    character: int


class LspRange(Contract):
    start: LspPosition
    end: LspPosition


class FileDiagnostic(Contract):
    path: str
    range: LspRange
    message: str
    severity: Severity


class Snapshot(Contract):
    """The schema as it was last read, or the reason there is none."""

    # `schema` is a method of BaseModel, so the attribute carries an underscore the wire does not.
    schema_: Schema | None = PydanticField(alias="schema")
    error: str | None
    diagnostics: list[FileDiagnostic]
    updated_at: datetime | str
    files: list[SchemaFile]
