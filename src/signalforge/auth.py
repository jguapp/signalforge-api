from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Mapping

from .domain.errors import AuthenticationError, AuthorizationError


@dataclass(frozen=True, slots=True)
class AuthContext:
    actor_id: str
    org_id: str
    scopes: frozenset[str]

    def require(self, scope: str) -> None:
        if scope not in self.scopes:
            raise AuthorizationError(f"scope {scope!r} is required")


class TokenAuthenticator:
    def __init__(self, tokens: Mapping[str, AuthContext]) -> None:
        self._tokens = dict(tokens)

    def authenticate(self, authorization: object) -> AuthContext:
        if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
            raise AuthenticationError("a bearer token is required")
        supplied = authorization.removeprefix("Bearer ").strip()
        for token, context in self._tokens.items():
            if hmac.compare_digest(supplied, token):
                return context
        raise AuthenticationError("the bearer token is invalid")

