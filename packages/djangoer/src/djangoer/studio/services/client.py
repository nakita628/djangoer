"""The Django ORM playground: a query read with `ast`, and run through the project's ORM."""

from __future__ import annotations

from .. import contract, inputs
from ..domain.orm import analyze as orm_analyze
from ..domain.orm import complete as orm_complete
from ..domain.orm import run as orm_run
from ..errors import QueryError
from .effect import effect, reading


def status(input: inputs.Input):
    return reading(contract.ClientStatus, lambda: orm_run.status(input))


def analyze(input: inputs.Query):
    return reading(contract.ClientAnalysis, lambda: orm_analyze.analyze(input))


def check(input: inputs.Query):
    return reading(contract.ClientTypeDiagnostics, lambda: orm_analyze.check(input))


def complete(input: inputs.QueryAt):
    return reading(contract.ClientCompletions, lambda: orm_complete.complete(input))


def detail(input: inputs.CompletionAt):
    return reading(contract.ClientCompletionDetail, lambda: orm_complete.detail(input))


def hover(input: inputs.QueryAt):
    return reading(contract.ClientHover, lambda: orm_complete.hover(input))


def signature(input: inputs.QueryAt):
    return reading(contract.ClientSignatureHelp, lambda: orm_complete.signature(input))


def preview(input: inputs.RunQuery):
    return effect(contract.ClientPreview, (QueryError,), lambda: orm_run.preview(input))


def run(input: inputs.RunQuery):
    return effect(contract.ClientResult, (QueryError,), lambda: orm_run.run(input))
