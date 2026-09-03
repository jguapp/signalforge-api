from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager

from ..domain.errors import ConflictError
from ..domain.models import Incident, IncidentStatus, MetricPoint, Monitor, OutboxMessage, OutboxStatus


class InMemoryDatabase:
    """A deterministic repository with rollback semantics for service tests.

    This is intentionally not presented as a production database. It gives the
    codebase a real transaction boundary without requiring external services.
    """

    def __init__(self) -> None:
        self._monitors: dict[str, Monitor] = {}
        self._points: dict[tuple[str, str], list[MetricPoint]] = {}
        self._incidents: dict[str, Incident] = {}
        self._outbox: dict[str, OutboxMessage] = {}

    @contextmanager
    def atomic(self) -> Iterator[None]:
        snapshot = (
            dict(self._monitors),
            {key: list(points) for key, points in self._points.items()},
            dict(self._incidents),
            dict(self._outbox),
        )
        try:
            yield
        except Exception:
            self._monitors, self._points, self._incidents, self._outbox = snapshot
            raise

    def add_monitor(self, monitor: Monitor) -> None:
        if monitor.id in self._monitors:
            raise ConflictError(f"monitor {monitor.id!r} already exists")
        self._monitors[monitor.id] = monitor

    def save_monitor(self, monitor: Monitor) -> None:
        self._monitors[monitor.id] = monitor

    def get_monitor(self, org_id: str, monitor_id: str) -> Monitor | None:
        monitor = self._monitors.get(monitor_id)
        return monitor if monitor is not None and monitor.org_id == org_id else None

    def find_monitor_by_name(self, org_id: str, name: str) -> Monitor | None:
        canonical = name.casefold()
        return next(
            (monitor for monitor in self._monitors.values() if monitor.org_id == org_id and monitor.name.casefold() == canonical),
            None,
        )

    def list_monitors(self, org_id: str) -> Sequence[Monitor]:
        return sorted(
            (monitor for monitor in self._monitors.values() if monitor.org_id == org_id),
            key=lambda monitor: (monitor.name.casefold(), monitor.id),
        )

    def list_monitors_for_metric(self, org_id: str, metric: str) -> Sequence[Monitor]:
        return [monitor for monitor in self.list_monitors(org_id) if monitor.metric == metric]

    def append_points(self, points: Sequence[MetricPoint]) -> None:
        for point in points:
            self._points.setdefault((point.org_id, point.metric), []).append(point)

    def recent_points(self, org_id: str, metric: str, limit: int) -> Sequence[MetricPoint]:
        points = sorted(self._points.get((org_id, metric), []), key=lambda point: point.timestamp)
        return points[-limit:]

    def add_incident(self, incident: Incident) -> None:
        if incident.id in self._incidents:
            raise ConflictError(f"incident {incident.id!r} already exists")
        self._incidents[incident.id] = incident

    def save_incident(self, incident: Incident) -> None:
        self._incidents[incident.id] = incident

    def get_incident(self, org_id: str, incident_id: str) -> Incident | None:
        incident = self._incidents.get(incident_id)
        return incident if incident is not None and incident.org_id == org_id else None

    def find_unresolved_incident(self, org_id: str, monitor_id: str) -> Incident | None:
        return next(
            (
                incident
                for incident in self._incidents.values()
                if incident.org_id == org_id
                and incident.monitor_id == monitor_id
                and incident.status is not IncidentStatus.RESOLVED
            ),
            None,
        )

    def list_incidents(self, org_id: str) -> Sequence[Incident]:
        return sorted(
            (incident for incident in self._incidents.values() if incident.org_id == org_id),
            key=lambda incident: (incident.opened_at, incident.id),
            reverse=True,
        )

    def add_outbox_message(self, message: OutboxMessage) -> None:
        if message.id in self._outbox:
            raise ConflictError(f"outbox message {message.id!r} already exists")
        self._outbox[message.id] = message

    def pending_outbox_messages(self, limit: int) -> Sequence[OutboxMessage]:
        pending = [message for message in self._outbox.values() if message.status is OutboxStatus.PENDING]
        return sorted(pending, key=lambda message: (message.created_at, message.id))[:limit]

    def save_outbox_message(self, message: OutboxMessage) -> None:
        self._outbox[message.id] = message

    def iter_all_incidents(self) -> Iterator[Incident]:
        """Administrative diagnostic access. Domain services should use scoped reads."""
        return iter(self._incidents.values())

    def counts(self) -> dict[str, int]:
        return {
            "monitors": len(self._monitors),
            "points": sum(len(points) for points in self._points.values()),
            "incidents": len(self._incidents),
            "pending_outbox": sum(message.status is OutboxStatus.PENDING for message in self._outbox.values()),
        }

