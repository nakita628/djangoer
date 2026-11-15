"""The reference page: every model with its fields and an example of each ORM operation."""

from __future__ import annotations

from typing import Literal

from .base import Contract
from .schema import FieldKind

DocsTypeLocation = Literal[
    "scalar", "inputObjectTypes", "outputObjectTypes", "enumTypes", "fieldRefTypes"
]


class DocsTypeRef(Contract):
    type: str
    is_list: bool
    location: DocsTypeLocation


class DocsDirective(Contract):
    name: str
    values: list[str]


class DocsField(Contract):
    name: str
    type: str
    bare_type_name: str
    kind: FieldKind
    directives: list[str]
    documentation: str | None
    required: bool


class DocsOperationInput(Contract):
    name: str
    types: list[DocsTypeRef]
    required: bool


class DocsOperationOutput(Contract):
    type: str | None
    required: bool
    list: bool


class DocsOperation(Contract):
    name: str
    description: str
    usage: str
    inputs: list[DocsOperationInput] | None
    output: DocsOperationOutput


class DocsModel(Contract):
    name: str
    documentation: str | None
    directives: list[DocsDirective]
    fields: list[DocsField]
    operations: list[DocsOperation]


class DocsTypeField(Contract):
    name: str
    types: list[DocsTypeRef]
    nullable: bool


class DocsObjectType(Contract):
    name: str
    fields: list[DocsTypeField]


class DocsEnum(Contract):
    name: str
    values: list[str]


class Docs(Contract):
    models: list[DocsModel]
    input_types: list[DocsObjectType]
    output_types: list[DocsObjectType]
    enum_types: list[DocsEnum]
