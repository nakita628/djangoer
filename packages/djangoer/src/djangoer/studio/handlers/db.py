"""`/api/db`: the status, the rows of a model, SQL, its plan and what it reads.

Each path operation matches the result of its use case: the value of a success is the answer,
and each error the use case can fail with is answered as its problem. The match on the error
ends in `assert_never`, so an error without a case is one the type checker names.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Query, Request
from returns.result import Failure, Success
from typing_extensions import assert_never

from .. import contract, inputs
from ..brands import ModelName
from ..errors import (
    DatabaseRejectedError,
    DatabaseUnavailableError,
    InvalidInputError,
    UnknownModelError,
)
from ..usecases import DatabaseUseCase
from . import problems
from .common import INVALID, NOT_FOUND, UNAVAILABLE, StudioState

# The path names the model as the client does (`modelName`); Python reads it as `model`.
Model = Annotated[ModelName, Path(alias="modelName")]

router = APIRouter(prefix="/db", tags=["db"])

ROW_PROBLEMS = {**NOT_FOUND, **INVALID, **UNAVAILABLE}
SQL_PROBLEMS = {**INVALID, **UNAVAILABLE}


@router.get("", operation_id="readDbStatus", response_model=contract.DbStatus)
def read_status(state: StudioState):
    match DatabaseUseCase.read_status(inputs.OnDatabase(alias=state.alias)):
        case Success(value):
            return value
        case Failure(error):
            assert_never(error)


@router.get(
    "/counts", operation_id="readCounts", response_model=contract.Counts, responses=UNAVAILABLE
)
def read_counts(request: Request, state: StudioState):
    match DatabaseUseCase.read_counts(inputs.OnDatabase(alias=state.alias)):
        case Success(value):
            return value
        case Failure(error):
            match error:
                case DatabaseUnavailableError():
                    return problems.unavailable(request, error)
                case _:
                    assert_never(error)


@router.get(
    "/rows/{modelName}",
    operation_id="readRows",
    response_model=contract.Rows,
    responses=ROW_PROBLEMS,
)
def read_rows(
    request: Request,
    state: StudioState,
    model: Model,
    query: Annotated[contract.RowsQuery, Query()],
):
    match DatabaseUseCase.read_rows(
        inputs.ReadRows(
            alias=state.alias, model=model, skip=query.skip, take=query.take, search=query.search
        )
    ):
        case Success(value):
            return value
        case Failure(error):
            match error:
                case DatabaseUnavailableError():
                    return problems.unavailable(request, error)
                case UnknownModelError():
                    return problems.not_found(request, error)
                case _:
                    assert_never(error)


@router.post(
    "/rows/{modelName}",
    operation_id="createRow",
    response_model=contract.Affected,
    responses=ROW_PROBLEMS,
)
def create_row(request: Request, state: StudioState, model: Model, body: contract.InsertBody):
    match DatabaseUseCase.create_row(
        inputs.CreateRow(alias=state.alias, model=model, values=body.values)
    ):
        case Success(value):
            return value
        case Failure(error):
            match error:
                case DatabaseUnavailableError():
                    return problems.unavailable(request, error)
                case UnknownModelError():
                    return problems.not_found(request, error)
                case InvalidInputError():
                    return problems.invalid(request, error)
                case DatabaseRejectedError():
                    return problems.rejected(request, error)
                case _:
                    assert_never(error)


@router.patch(
    "/rows/{modelName}",
    operation_id="updateRow",
    response_model=contract.Affected,
    responses=ROW_PROBLEMS,
)
def update_row(request: Request, state: StudioState, model: Model, body: contract.UpdateBody):
    match DatabaseUseCase.update_row(
        inputs.UpdateRow(alias=state.alias, model=model, where=body.where, values=body.values)
    ):
        case Success(value):
            return value
        case Failure(error):
            match error:
                case DatabaseUnavailableError():
                    return problems.unavailable(request, error)
                case UnknownModelError():
                    return problems.not_found(request, error)
                case InvalidInputError():
                    return problems.invalid(request, error)
                case DatabaseRejectedError():
                    return problems.rejected(request, error)
                case _:
                    assert_never(error)


@router.delete(
    "/rows/{modelName}",
    operation_id="deleteRow",
    response_model=contract.Affected,
    responses=ROW_PROBLEMS,
)
def delete_row(request: Request, state: StudioState, model: Model, body: contract.DeleteBody):
    match DatabaseUseCase.delete_row(
        inputs.DeleteRow(alias=state.alias, model=model, where=body.where)
    ):
        case Success(value):
            return value
        case Failure(error):
            match error:
                case DatabaseUnavailableError():
                    return problems.unavailable(request, error)
                case UnknownModelError():
                    return problems.not_found(request, error)
                case InvalidInputError():
                    return problems.invalid(request, error)
                case DatabaseRejectedError():
                    return problems.rejected(request, error)
                case _:
                    assert_never(error)


@router.post(
    "/sql", operation_id="runSql", response_model=contract.SqlResult, responses=SQL_PROBLEMS
)
def run_sql(request: Request, state: StudioState, body: contract.SqlBody):
    match DatabaseUseCase.run_sql(
        inputs.RunSql(alias=state.alias, sql=body.sql, params=body.params)
    ):
        case Success(value):
            return value
        case Failure(error):
            match error:
                case DatabaseUnavailableError():
                    return problems.unavailable(request, error)
                case InvalidInputError():
                    return problems.invalid(request, error)
                case DatabaseRejectedError():
                    return problems.rejected(request, error)
                case _:
                    assert_never(error)


@router.post(
    "/explain", operation_id="explainSql", response_model=contract.Plan, responses=SQL_PROBLEMS
)
def explain_sql(request: Request, state: StudioState, body: contract.SqlBody):
    match DatabaseUseCase.explain_sql(
        inputs.RunSql(alias=state.alias, sql=body.sql, params=body.params)
    ):
        case Success(value):
            return value
        case Failure(error):
            match error:
                case DatabaseUnavailableError():
                    return problems.unavailable(request, error)
                case InvalidInputError():
                    return problems.invalid(request, error)
                case DatabaseRejectedError():
                    return problems.rejected(request, error)
                case _:
                    assert_never(error)


@router.post(
    "/analyze", operation_id="analyzeSql", response_model=contract.Analysis, responses=INVALID
)
def analyze_sql(state: StudioState, body: contract.AnalyzeBody):
    match DatabaseUseCase.analyze_sql(inputs.AnalyzeSql(alias=state.alias, sql=body.sql)):
        case Success(value):
            return value
        case Failure(error):
            assert_never(error)
