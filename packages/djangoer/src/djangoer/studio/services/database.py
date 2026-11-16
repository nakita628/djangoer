"""The database, through Django's connection and ORM."""

from __future__ import annotations

from returns.result import Failure, Result, Success

from .. import contract, inputs
from ..domain import database, sqlanalysis
from ..errors import (
    DatabaseRejectedError,
    DatabaseUnavailableError,
    InvalidInputError,
    UnknownModelError,
)
from ..pipeline import then
from .effect import effect, reading


def status(input: inputs.OnDatabase):
    return reading(contract.DbStatus, lambda: database.status(input))


# Annotated, unlike the functions around it: the two branches are a Success and a Failure, and
# only the annotation says they are one Result.
def _answering(
    found: contract.DbStatus,
) -> Result[contract.DbStatus, DatabaseUnavailableError]:
    if found.connected:
        return Success(found)
    return Failure(DatabaseUnavailableError(f"The database cannot be reached: {found.error}"))


def connected(input: inputs.OnDatabase):
    """The status of a database that answers; a failure for one that does not."""
    return then(status(input), _answering)


def counts(input: inputs.OnDatabase):
    return reading(contract.Counts, lambda: database.counts(input))


def rows(input: inputs.ReadRows):
    return effect(
        contract.Rows,
        (UnknownModelError, DatabaseUnavailableError),
        lambda: database.rows(input),
    )


# What writing a row can fail with: no such model, a value its field refuses, a row the
# database refuses.
WRITE_ERRORS = (UnknownModelError, InvalidInputError, DatabaseRejectedError)
# What a statement can fail with: nothing to run, or SQL the database refuses.
SQL_ERRORS = (InvalidInputError, DatabaseRejectedError)


def insert(input: inputs.CreateRow):
    return effect(contract.Affected, WRITE_ERRORS, lambda: database.insert(input))


def update(input: inputs.UpdateRow):
    return effect(contract.Affected, WRITE_ERRORS, lambda: database.update(input))


def delete(input: inputs.DeleteRow):
    return effect(contract.Affected, WRITE_ERRORS, lambda: database.delete(input))


def run_sql(input: inputs.RunSql):
    return effect(contract.SqlResult, SQL_ERRORS, lambda: database.run_sql(input))


def explain(input: inputs.RunSql):
    return effect(
        contract.Plan,
        (*SQL_ERRORS, DatabaseUnavailableError),
        lambda: database.explain(input),
    )


def analyze(input: inputs.AnalyzeSql):
    return reading(contract.Analysis, lambda: sqlanalysis.analyze(input))
