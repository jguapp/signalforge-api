from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from .domain.errors import ValidationError


METRIC_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.-]{0,199}$")


def required_text(value: object, field: str, *, maximum: int = 200) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} must be a non-empty string")
    normalized = value.strip()
    if len(normalized) > maximum:
        raise ValidationError(f"{field} cannot exceed {maximum} characters")
    return normalized


def metric_name(value: object) -> str:
    metric = required_text(value, "metric")
    if not METRIC_PATTERN.fullmatch(metric):
        raise ValidationError("metric contains unsupported characters")
    return metric


def decimal_value(value: object, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValidationError(f"{field} must be numeric")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValidationError(f"{field} must be numeric") from None
    if not result.is_finite():
        raise ValidationError(f"{field} must be finite")
    return result


def bounded_integer(value: object, field: str, *, minimum: int, maximum: int) -> int:
    if type(value) is not int:
        raise ValidationError(f"{field} must be an integer")
    if value < minimum or value > maximum:
        raise ValidationError(f"{field} must be between {minimum} and {maximum}")
    return value


def aware_timestamp(value: object, field: str) -> datetime:
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValidationError(f"{field} must be an ISO-8601 timestamp") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValidationError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def normalized_tags(value: object) -> tuple[tuple[str, str], ...]:
    if value is None:
        return ()
    if not isinstance(value, dict) or len(value) > 25:
        raise ValidationError("tags must be an object with at most 25 entries")
    normalized: list[tuple[str, str]] = []
    for raw_key, raw_value in value.items():
        key = required_text(raw_key, "tag key", maximum=80)
        item = required_text(raw_value, f"tag {key!r}", maximum=200)
        normalized.append((key, item))
    return tuple(sorted(normalized))

