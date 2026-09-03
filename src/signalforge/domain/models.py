from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

from .errors import ConflictError


class Comparator(StrEnum):
    ABOVE = "above"
    AT_OR_ABOVE = "at_or_above"
    BELOW = "below"
    AT_OR_BELOW = "at_or_below"


class MonitorState(StrEnum):
    ACTIVE = "active"
    MUTED = "muted"


class IncidentStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class OutboxStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"


def isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class Monitor:
    id: str
    org_id: str
    name: str
    metric: str
    comparator: Comparator
    threshold: Decimal
    window_size: int
    state: MonitorState
    version: int
    created_at: datetime
    updated_at: datetime

    def update(
        self,
        *,
        name: str,
        comparator: Comparator,
        threshold: Decimal,
        window_size: int,
        state: MonitorState,
        now: datetime,
    ) -> "Monitor":
        return replace(
            self,
            name=name,
            comparator=comparator,
            threshold=threshold,
            window_size=window_size,
            state=state,
            version=self.version + 1,
            updated_at=now,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "metric": self.metric,
            "comparator": self.comparator.value,
            "threshold": str(self.threshold),
            "window_size": self.window_size,
            "state": self.state.value,
            "version": self.version,
            "created_at": isoformat(self.created_at),
            "updated_at": isoformat(self.updated_at),
        }


@dataclass(frozen=True, slots=True)
class MetricPoint:
    org_id: str
    metric: str
    value: Decimal
    timestamp: datetime
    tags: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class Incident:
    id: str
    org_id: str
    monitor_id: str
    monitor_name: str
    status: IncidentStatus
    trigger_value: Decimal
    opened_at: datetime
    updated_at: datetime
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    version: int = 1

    def acknowledge(self, *, actor_id: str, now: datetime) -> "Incident":
        if self.status is not IncidentStatus.OPEN:
            raise ConflictError(f"incident {self.id!r} is not open")
        return replace(
            self,
            status=IncidentStatus.ACKNOWLEDGED,
            acknowledged_by=actor_id,
            acknowledged_at=now,
            updated_at=now,
            version=self.version + 1,
        )

    def resolve(self, *, now: datetime) -> "Incident":
        if self.status is IncidentStatus.RESOLVED:
            return self
        return replace(
            self,
            status=IncidentStatus.RESOLVED,
            resolved_at=now,
            updated_at=now,
            version=self.version + 1,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "monitor_id": self.monitor_id,
            "monitor_name": self.monitor_name,
            "status": self.status.value,
            "trigger_value": str(self.trigger_value),
            "opened_at": isoformat(self.opened_at),
            "updated_at": isoformat(self.updated_at),
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": isoformat(self.acknowledged_at),
            "resolved_at": isoformat(self.resolved_at),
            "version": self.version,
        }


@dataclass(frozen=True, slots=True)
class OutboxMessage:
    id: str
    org_id: str
    topic: str
    payload: Mapping[str, object]
    created_at: datetime
    status: OutboxStatus = OutboxStatus.PENDING
    sent_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        id: str,
        org_id: str,
        topic: str,
        payload: Mapping[str, object],
        now: datetime,
    ) -> "OutboxMessage":
        return cls(id, org_id, topic, MappingProxyType(dict(payload)), now)

    def mark_sent(self, now: datetime) -> "OutboxMessage":
        return replace(self, status=OutboxStatus.SENT, sent_at=now)

