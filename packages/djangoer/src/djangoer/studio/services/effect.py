"""Where the outside world is touched: every effect is a `Result`, checked against its contract.

The domain answers with a `Result` wherever something can go wrong. A service says which errors
that can be, and they become the type of its failure, so that a handler can be held to
answering each of them. Nothing above the services has to catch.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from django.db import close_old_connections
from pydantic import BaseModel
from returns.result import Failure, Result, Success
from typing_extensions import Never

from ..errors import StudioError

C = TypeVar("C", bound=BaseModel)
E = TypeVar("E", bound=StudioError)
T = TypeVar("T")


def _with_connection(run: Callable[[], T]) -> T:
    """The database connection of this thread is checked before and released after, as Django
    does around a request: the server's worker threads outlive the requests they run."""
    close_old_connections()
    try:
        return run()
    finally:
        close_old_connections()


def effect(
    model: type[C],
    errors: tuple[type[E], ...],
    run: Callable[[], Result[Any, StudioError]],
) -> Result[C, E]:
    """Run an effect that can fail with one of `errors`, and check the value of its success
    against its contract.

    `errors` is the service's word for what the domain can answer: the type of the failure is
    exactly those. The domain is held to it when it runs: a failure of another kind is a bug
    of this server, raised as one, not passed on under a type that does not name it.
    """
    match _with_connection(run):
        case Success(value):
            return Success(model.model_validate(value))
        case Failure(error) if isinstance(error, errors):
            return Failure(error)
        case failed:
            raise TypeError(
                f"An effect declared to fail with {[kind.__name__ for kind in errors]} "
                f"answered {failed!r}."
            )


def reading(model: type[C], run: Callable[[], Any]) -> Result[C, Never]:
    """Run an effect with nothing to fail on, and check what it gives against its contract."""
    return Success(model.model_validate(_with_connection(run)))
