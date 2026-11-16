"""What the data pages and the SQL console ask for.

Each use case is a pipeline of `Result`s: the first failure is the answer, and the steps after
it are not run. A database that does not answer fails the pipeline before a table is touched.
What a pipeline can fail with is the errors of its steps together, by inference (pipeline.py):
the handler of the route matches on exactly those.
"""

from __future__ import annotations

from .. import inputs
from ..pipeline import then
from ..services import DatabaseService


def read_status(input: inputs.OnDatabase):
    """Whether the database answers: a status either way, never a failure of the request."""
    return DatabaseService.status(input)


def read_counts(input: inputs.OnDatabase):
    return then(DatabaseService.connected(input), lambda _: DatabaseService.counts(input))


def read_rows(input: inputs.ReadRows):
    return then(DatabaseService.connected(input), lambda _: DatabaseService.rows(input))


def create_row(input: inputs.CreateRow):
    return then(DatabaseService.connected(input), lambda _: DatabaseService.insert(input))


def update_row(input: inputs.UpdateRow):
    return then(DatabaseService.connected(input), lambda _: DatabaseService.update(input))


def delete_row(input: inputs.DeleteRow):
    return then(DatabaseService.connected(input), lambda _: DatabaseService.delete(input))


def run_sql(input: inputs.RunSql):
    return then(DatabaseService.connected(input), lambda _: DatabaseService.run_sql(input))


def explain_sql(input: inputs.RunSql):
    return then(DatabaseService.connected(input), lambda _: DatabaseService.explain(input))


def analyze_sql(input: inputs.AnalyzeSql):
    """What a statement reads, from its text alone: it needs no database that answers."""
    return DatabaseService.analyze(input)
