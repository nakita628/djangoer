"""The reference of every model."""

from __future__ import annotations

from .. import contract, inputs
from ..domain.docs import build_docs
from .effect import reading


def read(input: inputs.OnDatabase):
    return reading(contract.Docs, lambda: build_docs(input))
