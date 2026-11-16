"""`/api/export`: the diagram and the docs as files to save."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import Response
from returns.result import Failure, Success
from typing_extensions import assert_never

from .. import inputs
from ..errors import ExportError
from ..usecases import ExportUseCase
from . import problems
from .common import StudioState

router = APIRouter(prefix="/export", tags=["export"])


# Not in the OpenAPI document: a file is saved through a link, not read through a hook.
@router.get("/{name}", include_in_schema=False)
def download_file(request: Request, state: StudioState, name: str):
    match ExportUseCase.download_file(
        inputs.ExportFile(alias=state.alias, name=name, root=state.root)
    ):
        case Success(value):
            return Response(
                value.content,
                media_type=value.media_type,
                headers={"Content-Disposition": f'attachment; filename="{value.name}"'},
            )
        case Failure(error):
            match error:
                case ExportError():
                    return problems.no_export(request, error)
                case _:
                    assert_never(error)
