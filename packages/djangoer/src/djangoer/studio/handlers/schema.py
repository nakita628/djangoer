"""`/api/schema`: the models as Studio draws them, and the stream that says they changed."""

from __future__ import annotations

from fastapi import APIRouter
from returns.result import Failure, Success
from typing_extensions import assert_never

from .. import contract
from ..usecases import SchemaUseCase
from .common import StudioState, server_sent_events

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


# Not in the OpenAPI document: a stream is read with EventSource, not with a generated hook.
@router.get("/events", include_in_schema=False)
async def read_schema_events(state: StudioState):
    return server_sent_events(SchemaUseCase.watch_schema(state))
