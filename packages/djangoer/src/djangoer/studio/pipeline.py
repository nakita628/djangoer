"""One step after another, with the errors of both: what Effect's pipelines do for a `Result`.

`Result.bind` asks both steps for the same error type. `then` does not: the pipeline can fail
with what either step fails with, and its type says so, by inference:

    then(connected(input), lambda _: rows(input))
    # Result[Rows, DatabaseUnavailableError | UnknownModelError]

That union is what a handler matches on, and what the type checker holds it to: a case that is
missing is an error it names.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from returns.result import Failure, Result, Success

A = TypeVar("A")
B = TypeVar("B")
E1 = TypeVar("E1")
E2 = TypeVar("E2")


def then(first: Result[A, E1], following: Callable[[A], Result[B, E2]]) -> Result[B, E1 | E2]:
    """`following` on the value of a success; the failure, untouched, otherwise."""
    match first:
        case Success(value):
            return following(value)
        case Failure(error):
            return Failure(error)
        case _:
            raise TypeError(f"{type(first).__name__} is not a Result.")
