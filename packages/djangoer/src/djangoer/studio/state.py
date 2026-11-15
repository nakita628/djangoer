"""What Studio holds between requests: the schema as last read, and a count of its changes."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path

from . import contract
from .brands import Alias
from .domain.schema import broken_snapshot, build_snapshot


@dataclass
class State:
    """One per server. The snapshot is replaced, never changed, so a reader keeps a whole one."""

    alias: Alias
    root: Path
    # Why the project did not load, when it did not: Studio then serves only that, and waits
    # for the file to be fixed (the process restarts when it changes).
    failure: BaseException | None = None
    snapshot: contract.Snapshot = field(init=False)
    version: int = field(default=0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        self.snapshot = self._read()

    def _read(self) -> contract.Snapshot:
        if self.failure is not None:
            return contract.Snapshot.model_validate(broken_snapshot(self.failure, self.root))
        return contract.Snapshot.model_validate(build_snapshot(self.alias, self.root))

    def reload(self) -> contract.Snapshot:
        snapshot = self._read()
        with self._lock:
            self.snapshot = snapshot
            self.version += 1
        return snapshot
