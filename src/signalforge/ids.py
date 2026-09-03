from __future__ import annotations

import secrets
from collections import defaultdict
from typing import Protocol


class IdGenerator(Protocol):
    def new(self, prefix: str) -> str: ...


class RandomIdGenerator:
    def new(self, prefix: str) -> str:
        return f"{prefix}_{secrets.token_hex(8)}"


class SequentialIdGenerator:
    def __init__(self) -> None:
        self._next: dict[str, int] = defaultdict(int)

    def new(self, prefix: str) -> str:
        self._next[prefix] += 1
        return f"{prefix}_{self._next[prefix]:04d}"

