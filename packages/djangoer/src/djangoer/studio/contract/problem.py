"""RFC 9457 problem details, the body of every answer that is not a success."""

from __future__ import annotations

from typing import Literal

from .base import Contract


class FieldError(Contract):
    field: str
    message: str


class Problem(Contract):
    """What every problem says: what went wrong, and for which request. Its `type`, `title` and
    `status` are constants of each kind of problem, below."""

    detail: str
    instance: str


class ValidationProblem(Problem):
    type: Literal["/problems/validation-failed"] = "/problems/validation-failed"
    title: Literal["Validation Failed"] = "Validation Failed"
    status: Literal[422] = 422
    errors: list[FieldError]


class NotFoundProblem(Problem):
    type: Literal["/problems/not-found"] = "/problems/not-found"
    title: Literal["Not Found"] = "Not Found"
    status: Literal[404] = 404


class ServiceUnavailableProblem(Problem):
    type: Literal["/problems/service-unavailable"] = "/problems/service-unavailable"
    title: Literal["Service Unavailable"] = "Service Unavailable"
    status: Literal[503] = 503


class InternalServerProblem(Problem):
    type: Literal["/problems/internal-server-error"] = "/problems/internal-server-error"
    title: Literal["Internal Server Error"] = "Internal Server Error"
    status: Literal[500] = 500


# One of the four: what a handler answers with when it does not answer with its contract.
AnyProblem = NotFoundProblem | ValidationProblem | ServiceUnavailableProblem | InternalServerProblem
