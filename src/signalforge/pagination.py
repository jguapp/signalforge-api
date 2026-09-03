from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime

from .domain.errors import ValidationError
from .validation import aware_timestamp


@dataclass(frozen=True, slots=True)
class IncidentCursor:
    opened_at: datetime
    incident_id: str


def encode_incident_cursor(cursor: IncidentCursor) -> str:
    payload = json.dumps(
        {"opened_at": cursor.opened_at.isoformat(), "incident_id": cursor.incident_id},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_incident_cursor(value: object) -> IncidentCursor | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or len(value) > 500:
        raise ValidationError("cursor is invalid")
    try:
        padded = value + "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        if not isinstance(payload, dict) or set(payload) != {"opened_at", "incident_id"}:
            raise ValueError
        incident_id = payload["incident_id"]
        if not isinstance(incident_id, str) or not incident_id:
            raise ValueError
        return IncidentCursor(aware_timestamp(payload["opened_at"], "cursor.opened_at"), incident_id)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise ValidationError("cursor is invalid") from None

