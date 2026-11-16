"""What can go wrong, as values: each error is a small frozen record with a tag of its own.

They are not exceptions. The domain returns them in a `Failure`, the use cases pass them along a
pipeline, and the handlers match on them to answer with the HTTP problem each one is.
"""

from __future__ import annotations

from dataclasses import dataclass


class StudioError:
    """The base of every error Studio expects. Anything raised instead is a bug and answers 500."""


@dataclass(frozen=True)
class FieldProblem:
    field: str
    message: str


@dataclass(frozen=True)
class UnknownModelError(StudioError):
    """A model name the schema does not hold; raised before a table is touched."""

    model: str

    def __str__(self) -> str:
        return f'Unknown model "{self.model}".'


@dataclass(frozen=True)
class InvalidInputError(StudioError):
    """Request fields that cannot be run as given: an unknown column, a value its field refuses,
    an empty `where`."""

    problems: tuple[FieldProblem, ...]

    def __str__(self) -> str:
        return "The request failed validation. See `errors` for the offending fields."

    @staticmethod
    def of(field: str, message: str) -> InvalidInputError:
        return InvalidInputError((FieldProblem(field, message),))


@dataclass(frozen=True)
class DatabaseRejectedError(StudioError):
    """A statement or a write the database refused: a broken constraint, SQL that does not parse,
    a row an `on_delete=PROTECT` keeps."""

    field: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class DatabaseUnavailableError(StudioError):
    """The database cannot be reached, or cannot do what was asked (a plan on another backend)."""

    reason: str

    def __str__(self) -> str:
        return self.reason


@dataclass(frozen=True)
class QueryError(StudioError):
    """An ORM query that may not run (an import, a private name) or that raised when it ran."""

    messages: tuple[str, ...]

    def __str__(self) -> str:
        return self.messages[0] if self.messages else "The query could not be run."


@dataclass(frozen=True)
class ExportError(StudioError):
    """A file that cannot be written as asked: an extension no format has, a PNG without the
    package that draws it."""

    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class UnknownFileError(StudioError):
    """A path that is not one of the project's own model files; raised before anything is written."""

    path: str

    def __str__(self) -> str:
        return f'"{self.path}" is not one of the project\'s model files.'


@dataclass(frozen=True)
class FileWriteError(StudioError):
    """A model file the system refused to write: no permission, a disk that is full."""

    path: str
    cause: str

    def __str__(self) -> str:
        return f"{self.path} could not be written: {self.cause}"
