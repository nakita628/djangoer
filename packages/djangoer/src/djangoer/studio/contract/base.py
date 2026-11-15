"""The base of every model of the API: snake_case in Python, camelCase on the wire."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class Contract(BaseModel):
    """A value the API takes or gives. Frozen, and strict about its keys: a response the domain
    built with a key the contract does not name is a contract violation, not a silent extra."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )


# A table cell: a string, a number, a boolean or null. Whatever else a row carries is written
# as the string a person would type for it (domain/values.py).
Cell = str | int | float | bool | None
Row = dict[str, Cell]

NonNegativeInt = Annotated[int, Field(ge=0)]


class TextRange(Contract):
    """Character offsets into the text that was sent, end-exclusive."""

    start: int
    end: int
