"""The one place an exception of Django or of the database becomes a value."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from returns.result import Result, safe

from ..errors import StudioError

T = TypeVar("T")


def attempt(
    run: Callable[[], T],
    exceptions: tuple[type[Exception], ...],
    on_error: Callable[[Exception], StudioError],
) -> Result[T, StudioError]:
    """Run an effect: its value in a `Success`, or the error one of `exceptions` is, in a
    `Failure`. Any other exception is not expected here and goes on being raised."""
    return safe(exceptions=exceptions)(run)().alt(on_error)
