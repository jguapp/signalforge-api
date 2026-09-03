from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Pattern

from .http import Request, Response
from ..auth import AuthContext


Handler = Callable[[Request, AuthContext | None, dict[str, str]], Response]


@dataclass(frozen=True, slots=True)
class Route:
    method: str
    pattern: Pattern[str]
    handler: Handler
    public: bool = False

    @classmethod
    def create(cls, method: str, pattern: str, handler: Handler, *, public: bool = False) -> "Route":
        return cls(method, re.compile(f"^{pattern}$"), handler, public)


class Router:
    def __init__(self, routes: list[Route]) -> None:
        self._routes = list(routes)

    def match(self, method: str, path: str) -> tuple[Route | None, dict[str, str]]:
        for route in self._routes:
            match = route.pattern.fullmatch(path)
            if match is not None and route.method == method:
                return route, match.groupdict()
        return None, {}

    def allowed_methods(self, path: str) -> tuple[str, ...]:
        return tuple(sorted({route.method for route in self._routes if route.pattern.fullmatch(path)}))

