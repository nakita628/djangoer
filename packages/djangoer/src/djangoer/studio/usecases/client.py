"""What the Django ORM playground asks for."""

from __future__ import annotations

from returns.result import Success

from .. import contract, inputs
from ..pipeline import then
from ..services import ClientService, DatabaseService


def read_status(input: inputs.Input):
    return ClientService.status(input)


def analyze_query(input: inputs.Query):
    return ClientService.analyze(input)


def check_query(input: inputs.Query):
    return ClientService.check(input)


def complete_query(input: inputs.QueryAt):
    return ClientService.complete(input)


def detail_completion(
    input: inputs.CompletionAt,
):
    return ClientService.detail(input)


def hover_query(input: inputs.QueryAt):
    return ClientService.hover(input)


def signature_query(input: inputs.QueryAt):
    return ClientService.signature(input)


def format_query(input: inputs.Query):
    """The query's own layout, without what no one means to keep: trailing spaces, blank ends."""
    text = "\n".join(line.rstrip() for line in input.query.strip("\n").split("\n"))
    return Success(contract.ClientFormatted(text=text))


def preview_query(input: inputs.RunQuery):
    """The SQL a read sends. A write is not run on the way to a preview (domain/orm/run.py)."""
    return then(DatabaseService.connected(input), lambda _: ClientService.preview(input))


def run_query(input: inputs.RunQuery):
    return then(DatabaseService.connected(input), lambda _: ClientService.run(input))
