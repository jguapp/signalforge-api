from __future__ import annotations

from dataclasses import dataclass

from ..auth import AuthContext
from ..clock import Clock
from ..domain.errors import ConflictError, NotFoundError, ValidationError
from ..domain.models import Incident, IncidentStatus
from ..pagination import IncidentCursor, decode_incident_cursor, encode_incident_cursor
from ..repositories.protocols import Database


@dataclass(frozen=True, slots=True)
class IncidentPage:
    items: tuple[Incident, ...]
    next_cursor: str | None


class IncidentService:
    def __init__(self, database: Database, clock: Clock) -> None:
        self._database = database
        self._clock = clock

    def get(self, context: AuthContext, incident_id: str) -> Incident:
        context.require("incidents:read")
        return self._required_incident(context.org_id, incident_id)

    def list(
        self,
        context: AuthContext,
        *,
        status: object = None,
        limit: object = 25,
        cursor: object = None,
    ) -> IncidentPage:
        context.require("incidents:read")
        page_limit = self._limit(limit)
        requested_status = self._status(status)
        decoded = decode_incident_cursor(cursor)
        incidents = list(self._database.list_incidents(context.org_id))
        if requested_status is not None:
            incidents = [incident for incident in incidents if incident.status is requested_status]
        if decoded is not None:
            boundary = (decoded.opened_at, decoded.incident_id)
            incidents = [incident for incident in incidents if (incident.opened_at, incident.id) < boundary]
        page = incidents[: page_limit + 1]
        has_more = len(page) > page_limit
        items = tuple(page[:page_limit])
        next_cursor = None
        if has_more and items:
            last = items[-1]
            next_cursor = encode_incident_cursor(IncidentCursor(last.opened_at, last.id))
        return IncidentPage(items, next_cursor)

    def acknowledge(self, context: AuthContext, incident_id: str, data: dict[str, object]) -> Incident:
        context.require("incidents:write")
        incident = self._required_incident(context.org_id, incident_id)
        version = data.get("version")
        if type(version) is not int:
            raise ValidationError("version must be an integer")
        if version != incident.version:
            raise ConflictError("incident was modified; reload it and try again")
        updated = incident.acknowledge(actor_id=context.actor_id, now=self._clock.now())
        self._database.save_incident(updated)
        return updated

    def _required_incident(self, org_id: str, incident_id: str) -> Incident:
        incident = self._database.get_incident(org_id, incident_id)
        if incident is None:
            raise NotFoundError(f"incident {incident_id!r} was not found")
        return incident

    @staticmethod
    def _limit(value: object) -> int:
        if isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                raise ValidationError("limit must be an integer") from None
        if type(value) is not int or value < 1 or value > 100:
            raise ValidationError("limit must be between 1 and 100")
        return value

    @staticmethod
    def _status(value: object) -> IncidentStatus | None:
        if value in (None, ""):
            return None
        try:
            return IncidentStatus(value)
        except (ValueError, TypeError):
            allowed = ", ".join(item.value for item in IncidentStatus)
            raise ValidationError(f"status must be one of: {allowed}") from None

