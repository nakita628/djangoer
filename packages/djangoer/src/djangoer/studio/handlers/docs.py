"""`/api/docs`: the reference of every model."""

from __future__ import annotations

from fastapi import APIRouter
from returns.result import Failure, Success
from typing_extensions import assert_never

from .. import contract, inputs
from ..usecases import DocsUseCase
from .common import StudioState

router = APIRouter(prefix="/docs", tags=["docs"])


@router.get("", operation_id="readDocs", response_model=contract.Docs)
def read_docs(state: StudioState):
    match DocsUseCase.read_docs(inputs.OnDatabase(alias=state.alias)):
        case Success(value):
            return value
        case Failure(error):
            assert_never(error)
