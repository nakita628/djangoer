"""The schema Studio draws: Django models as models, fields, enums and relations."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field as PydanticField

from ..brands import Offset
from .base import Contract

FieldKind = Literal["scalar", "object", "enum", "unsupported"]
IndexType = Literal["id", "unique", "normal", "fulltext", "exclusion"]
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
    # The model a many-to-many goes through when it is one of the project's (`through=`).
    through: str | None


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
    # The default Python gives a new row; `db_default` is the one of the database, as SQL.
    default: str | None
    db_default: str | None
    # The expression of a generated column, as SQL: `"price" + "tax"`.
    generated: str | None
    native_type: str | None
    # A generated column: stored on disk (True) or computed on read (False).
    stored: bool | None
    # `db_collation`: how the column compares and sorts (`NOCASE`, `und-x-icu`).
    collation: str | None
    # What a DecimalField declares, which a type with no precision (SQLite's `decimal`) loses.
    max_digits: int | None
    decimal_places: int | None
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
    # How it is made: its method when not a B-tree (`gin`, `brin`, `hnsw`), the columns it
    # includes, and its storage parameters (`m = 16`).
    method: str | None
    include: list[str]
    parameters: list[str]
    # The columns in descending order (`fields=["-price"]`).
    descending: list[str]
    # A constraint checked at the end of the transaction: `deferred` or `immediate` at first.
    deferrable: str | None
    # `nulls_distinct=`: False is "NULLs count as equal". None when the model does not say.
    nulls_distinct: bool | None
    attribute: str


class Check(Contract):
    """A `CheckConstraint`: what every row must satisfy, as SQL."""

    name: str
    expression: str


class GenericForeignKey(Contract):
    """A pair of columns that names a row of any model: `content_object` is the row whose
    content type is in `content_type_id` and whose key is in `object_id`."""

    name: str
    content_type_field: str
    object_id_field: str


class ProxyModel(Contract):
    """A proxy of a model (`Meta.proxy = True`): its rows under another name, no table."""

    name: str
    app: str
    documentation: str | None


class AbstractBase(Contract):
    """An abstract model a model takes columns from (`Timestamped`), and which columns."""

    name: str
    fields: list[str]


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
    checks: list[Check]
    proxies: list[ProxyModel]
    abstract_bases: list[AbstractBase]
    # False for `managed = False`: Django neither creates nor changes the table.
    managed: bool
    attributes: list[str]
    location: Location | None
    # The project's own model, not an installed package's: in the project's directory.
    own: bool


class EnumValue(Contract):
    name: str
    db_name: str | None
    # The group of grouped choices it is in (`"Audio"`), None when they are not grouped.
    group: str | None


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
    # Whether the database has a foreign key for it: not for `db_constraint=False`, a
    # ForeignObject or a generic relation.
    constrained: bool
    # Multi-table inheritance: the child (`to`) is the parent (`from`), its rows joined on it.
    parent_link: bool


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
