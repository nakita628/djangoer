"""`/api/client`: the Django ORM playground."""

from __future__ import annotations

from fastapi import APIRouter, Request
from returns.result import Failure, Success
from typing_extensions import assert_never

from .. import contract, inputs
from ..errors import DatabaseUnavailableError, QueryError
from ..usecases import ClientUseCase
from . import problems
from .common import INVALID, UNAVAILABLE, StudioState

router = APIRouter(prefix="/client", tags=["client"])

RUN_PROBLEMS = {**INVALID, **UNAVAILABLE}


@router.get("", operation_id="readClientStatus", response_model=contract.ClientStatus)
def read_status():
    match ClientUseCase.read_status(inputs.Input()):
        case Success(value):
            return value
        case Failure(error):
            assert_never(error)


@router.post(
    "/analyze",
    operation_id="analyzeClientQuery",
    response_model=contract.ClientAnalysis,
    responses=INVALID,
)
def analyze_query(body: contract.ClientQueryBody):
    match ClientUseCase.analyze_query(inputs.Query(query=body.query)):
        case Success(value):
            return value
        case Failure(error):
            assert_never(error)


@router.post(
    "/check",
    operation_id="checkClientQuery",
    response_model=contract.ClientTypeDiagnostics,
    responses=INVALID,
)
def check_query(body: contract.ClientQueryBody):
    match ClientUseCase.check_query(inputs.Query(query=body.query)):
        case Success(value):
            return value
        case Failure(error):
            assert_never(error)


@router.post(
    "/complete",
    operation_id="completeClientQuery",
    response_model=contract.ClientCompletions,
    responses=INVALID,
)
def complete_query(body: contract.ClientPositionBody):
    match ClientUseCase.complete_query(inputs.QueryAt(query=body.query, offset=body.offset)):
        case Success(value):
            return value
        case Failure(error):
            assert_never(error)


@router.post(
    "/complete/detail",
    operation_id="detailClientCompletion",
    response_model=contract.ClientCompletionDetail,
    responses=INVALID,
)
def detail_completion(body: contract.ClientCompletionDetailBody):
    match ClientUseCase.detail_completion(
        inputs.CompletionAt(query=body.query, offset=body.offset, name=body.name)
    ):
        case Success(value):
            return value
        case Failure(error):
            assert_never(error)


@router.post(
    "/hover",
    operation_id="hoverClientQuery",
    response_model=contract.ClientHover,
    responses=INVALID,
)
def hover_query(body: contract.ClientPositionBody):
    match ClientUseCase.hover_query(inputs.QueryAt(query=body.query, offset=body.offset)):
        case Success(value):
            return value
        case Failure(error):
            assert_never(error)


@router.post(
    "/signature",
    operation_id="signatureClientQuery",
    response_model=contract.ClientSignatureHelp,
    responses=INVALID,
)
def signature_query(body: contract.ClientPositionBody):
    match ClientUseCase.signature_query(inputs.QueryAt(query=body.query, offset=body.offset)):
        case Success(value):
            return value
        case Failure(error):
            assert_never(error)


@router.post(
    "/format",
    operation_id="formatClientQuery",
    response_model=contract.ClientFormatted,
    responses=INVALID,
)
def format_query(body: contract.ClientQueryBody):
    match ClientUseCase.format_query(inputs.Query(query=body.query)):
        case Success(value):
            return value
        case Failure(error):
            assert_never(error)


@router.post(
    "/preview",
    operation_id="previewClientQuery",
    response_model=contract.ClientPreview,
    responses=RUN_PROBLEMS,
)
def preview_query(request: Request, state: StudioState, body: contract.ClientRunBody):
    match ClientUseCase.preview_query(inputs.RunQuery(alias=state.alias, query=body.query)):
        case Success(value):
            return value
        case Failure(error):
            match error:
                case DatabaseUnavailableError():
                    return problems.unavailable(request, error)
                case QueryError():
                    return problems.refused(request, error)
                case _:
                    assert_never(error)


@router.post(
    "/run",
    operation_id="runClientQuery",
    response_model=contract.ClientResult,
    responses=RUN_PROBLEMS,
)
def run_query(request: Request, state: StudioState, body: contract.ClientRunBody):
    match ClientUseCase.run_query(inputs.RunQuery(alias=state.alias, query=body.query)):
        case Success(value):
            return value
        case Failure(error):
            match error:
                case DatabaseUnavailableError():
                    return problems.unavailable(request, error)
                case QueryError():
                    return problems.refused(request, error)
                case _:
                    assert_never(error)
