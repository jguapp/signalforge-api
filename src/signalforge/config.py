from __future__ import annotations

import os
from dataclasses import dataclass

from .domain.errors import ValidationError


@dataclass(frozen=True, slots=True)
class Config:
    host: str = "127.0.0.1"
    port: int = 8010
    max_body_bytes: int = 1_000_000
    max_points_per_request: int = 500

    @classmethod
    def from_environment(cls) -> "Config":
        return cls(
            host=os.getenv("SIGNALFORGE_HOST", "127.0.0.1"),
            port=_positive_integer("SIGNALFORGE_PORT", 8010),
            max_body_bytes=_positive_integer("SIGNALFORGE_MAX_BODY_BYTES", 1_000_000),
            max_points_per_request=_positive_integer("SIGNALFORGE_MAX_POINTS", 500),
        )


def _positive_integer(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValidationError(f"{name} must be an integer") from None
    if value < 1:
        raise ValidationError(f"{name} must be positive")
    return value

