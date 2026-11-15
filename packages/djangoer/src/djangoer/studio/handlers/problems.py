"""Errors as HTTP: the RFC 9457 problem each error is answered with.

A handler matches the errors its use case can fail with, and answers each with the function
of that error here. What FastAPI itself refuses (a body that does not validate, a path no route
serves) is answered the same way, by the exception handlers at the end.
"""

from __future__ import annotations

import traceback
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from .. import contract
from ..errors import (
    DatabaseRejectedError,
    DatabaseUnavailableError,
    InvalidInputError,
    QueryError,
    UnknownModelError,
)

PROBLEM_JSON = "application/problem+json"


def answer(problem: contract.AnyProblem) -> JSONResponse:
    return JSONResponse(
        problem.model_dump(by_alias=True), status_code=problem.status, media_type=PROBLEM_JSON
    )


def _invalid(instance: str, errors: Sequence[tuple[str, str]], detail: str | None = None):
    return contract.ValidationProblem(
        detail=detail or "The request failed validation. See `errors` for the offending fields.",
        instance=instance,
        errors=[contract.FieldError(field=name, message=message) for name, message in errors],
    )


# One function per error: the problem a handler answers with when it matches that error.


def not_found(request: Request, error: UnknownModelError) -> JSONResponse:
    return answer(contract.NotFoundProblem(detail=str(error), instance=request.url.path))


def invalid(request: Request, error: InvalidInputError) -> JSONResponse:
    return answer(
        _invalid(request.url.path, [(problem.field, problem.message) for problem in error.problems])
    )


def rejected(request: Request, error: DatabaseRejectedError) -> JSONResponse:
    return answer(_invalid(request.url.path, [(error.field, error.message)], detail=error.message))


def refused(request: Request, error: QueryError) -> JSONResponse:
    return answer(
        _invalid(
            request.url.path, [("query", message) for message in error.messages], detail=str(error)
        )
    )


def unavailable(request: Request, error: DatabaseUnavailableError) -> JSONResponse:
    return answer(contract.ServiceUnavailableProblem(detail=str(error), instance=request.url.path))


def _field(location: Sequence[Any]) -> str:
    """`("query", "take")` is `take`; `("body",)` alone is the body itself."""
    parts = [str(part) for part in location if part not in ("body", "query", "path")]
    return ".".join(parts) or "body"


def no_route(request: Request) -> JSONResponse:
    """The answer for a path of the API that no route serves."""
    detail = f"No route for {request.method} {request.url.path}."
    return answer(contract.NotFoundProblem(detail=detail, instance=request.url.path))


def register(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    def request_invalid(request: Request, error: RequestValidationError) -> JSONResponse:
        # The message is the one Pydantic gives: "Input should be less than or equal to 1000".
        errors = [
            (_field(item.get("loc", ())), str(item.get("msg", ""))) for item in error.errors()
        ]
        return answer(_invalid(request.url.path, errors))

    @app.exception_handler(HTTPException)
    def http_error(request: Request, error: HTTPException) -> JSONResponse:
        if error.status_code == 404:
            return no_route(request)
        return JSONResponse({"detail": error.detail}, status_code=error.status_code)

    @app.exception_handler(Exception)
    def unexpected(request: Request, error: Exception) -> JSONResponse:
        # Not an error Studio expects: a bug, or a response that broke its contract.
        traceback.print_exception(error)
        detail = f"{type(error).__name__}: {error}"
        return answer(contract.InternalServerProblem(detail=detail, instance=request.url.path))
