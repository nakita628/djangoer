"""`/api/schema`: the models as Studio draws them, and the stream that says they changed."""

from __future__ import annotations

from fastapi import APIRouter, Request
from returns.result import Failure, Success
from typing_extensions import assert_never

from .. import contract, inputs
from ..errors import FileWriteError, PreviewError, UnknownFileError
from ..usecases import SchemaUseCase
from . import problems
from .common import INVALID, NOT_FOUND, StudioState, server_sent_events

router = APIRouter(prefix="/schema", tags=["schema"])


@router.get("", operation_id="readSchema", response_model=contract.Snapshot)
def read_schema(state: StudioState):
    match SchemaUseCase.read_schema(state):
        case Success(value):
            return value
        case Failure(error):
            assert_never(error)


@router.post("/reload", operation_id="reloadSchema", response_model=contract.Snapshot)
def reload_schema(state: StudioState):
    match SchemaUseCase.reload_schema(state):
        case Success(value):
            return value
        case Failure(error):
            assert_never(error)


@router.put(
    "/files",
    operation_id="writeSchemaFile",
    response_model=contract.SchemaFile,
    responses={**NOT_FOUND, **INVALID},
)
def write_schema_file(request: Request, state: StudioState, body: contract.FileWrite):
    match SchemaUseCase.write_schema_file(
        inputs.WriteFile(
            path=body.path,
            content=body.content,
            root=state.root,
            files=tuple(file.path for file in state.snapshot.files),
        )
    ):
        case Success(value):
            return value
        case Failure(error):
            match error:
                case UnknownFileError():
                    return problems.unknown_file(request, error)
                case FileWriteError():
                    return problems.not_written(request, error)
                case _:
                    assert_never(error)


@router.post(
    "/complete",
    operation_id="completeSchemaSource",
    response_model=contract.ClientCompletions,
    responses=INVALID,
)
def complete_source(state: StudioState, body: contract.SourcePositionBody):
    match SchemaUseCase.complete_source(
        inputs.SourceAt(path=body.path, content=body.content, offset=body.offset, root=state.root)
    ):
        case Success(value):
            return value
        case Failure(error):
            assert_never(error)


@router.post(
    "/hover",
    operation_id="hoverSchemaSource",
    response_model=contract.ClientHover,
    responses=INVALID,
)
def hover_source(state: StudioState, body: contract.SourcePositionBody):
    match SchemaUseCase.hover_source(
        inputs.SourceAt(path=body.path, content=body.content, offset=body.offset, root=state.root)
    ):
        case Success(value):
            return value
        case Failure(error):
            assert_never(error)


@router.post(
    "/check",
    operation_id="checkSchemaSource",
    response_model=contract.ClientTypeDiagnostics,
    responses=INVALID,
)
def check_source(state: StudioState, body: contract.SourceBody):
    match SchemaUseCase.check_source(
        inputs.SourceText(path=body.path, content=body.content, root=state.root)
    ):
        case Success(value):
            return value
        case Failure(error):
            assert_never(error)


@router.post(
    "/preview",
    operation_id="previewSchema",
    response_model=contract.Schema,
    responses=INVALID,
)
def preview_schema(request: Request, state: StudioState, body: contract.SourceBody):
    match SchemaUseCase.preview_schema(
        inputs.PreviewSource(
            alias=state.alias, path=body.path, content=body.content, root=state.root
        )
    ):
        case Success(value):
            return value
        case Failure(error):
            match error:
                case PreviewError():
                    return problems.not_loading(request, error)
                case _:
                    assert_never(error)


# Not in the OpenAPI document: a stream is read with EventSource, not with a generated hook.
@router.get("/events", include_in_schema=False)
async def read_schema_events(state: StudioState):
    return server_sent_events(SchemaUseCase.watch_schema(state))
