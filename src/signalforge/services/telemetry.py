from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from ..auth import AuthContext
from ..clock import Clock
from ..domain.errors import ValidationError
from ..domain.models import Incident, IncidentStatus, MetricPoint, MonitorState, OutboxMessage
from ..domain.policies import window_is_breaching
from ..ids import IdGenerator
from ..repositories.protocols import Database
from ..validation import aware_timestamp, decimal_value, metric_name, normalized_tags


@dataclass(frozen=True, slots=True)
class IngestResult:
    accepted_points: int
    opened_incident_ids: tuple[str, ...]
    resolved_incident_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "accepted_points": self.accepted_points,
            "opened_incident_ids": list(self.opened_incident_ids),
            "resolved_incident_ids": list(self.resolved_incident_ids),
        }


class TelemetryService:
    def __init__(
        self,
        database: Database,
        clock: Clock,
        ids: IdGenerator,
        *,
        max_points_per_request: int = 500,
    ) -> None:
        self._database = database
        self._clock = clock
        self._ids = ids
        self._max_points = max_points_per_request

    def ingest(self, context: AuthContext, data: dict[str, object]) -> IngestResult:
        context.require("telemetry:write")
        points = self._parse_points(context.org_id, data)
        touched_metrics = sorted({point.metric for point in points})
        opened: list[str] = []
        resolved: list[str] = []

        with self._database.atomic():
            self._database.append_points(points)
            for metric in touched_metrics:
                for monitor in self._database.list_monitors_for_metric(context.org_id, metric):
                    if monitor.state is MonitorState.MUTED:
                        continue
                    recent = self._database.recent_points(context.org_id, metric, monitor.window_size)
                    active_incident = self._database.find_unresolved_incident(context.org_id, monitor.id)
                    if window_is_breaching(monitor, recent) and active_incident is None:
                        incident = self._open_incident(context.org_id, monitor.id, monitor.name, recent[-1])
                        opened.append(incident.id)
                    elif not window_is_breaching(monitor, recent) and active_incident is not None:
                        updated = active_incident.resolve(now=self._clock.now())
                        self._database.save_incident(updated)
                        self._enqueue(context.org_id, "incident.resolved", updated)
                        resolved.append(updated.id)

        return IngestResult(len(points), tuple(opened), tuple(resolved))

    def _parse_points(self, org_id: str, data: dict[str, object]) -> list[MetricPoint]:
        series = data.get("series")
        if not isinstance(series, list) or not series:
            raise ValidationError("series must be a non-empty list")
        parsed: list[MetricPoint] = []
        now = self._clock.now()
        for series_index, raw_series in enumerate(series):
            if not isinstance(raw_series, dict):
                raise ValidationError(f"series[{series_index}] must be an object")
            metric = metric_name(raw_series.get("metric"))
            tags = normalized_tags(raw_series.get("tags"))
            raw_points = raw_series.get("points")
            if not isinstance(raw_points, list) or not raw_points:
                raise ValidationError(f"series[{series_index}].points must be a non-empty list")
            for point_index, raw_point in enumerate(raw_points):
                if not isinstance(raw_point, dict):
                    raise ValidationError(f"series[{series_index}].points[{point_index}] must be an object")
                timestamp = aware_timestamp(raw_point.get("timestamp"), "timestamp")
                if timestamp > now + timedelta(minutes=5):
                    raise ValidationError("point timestamps cannot be more than five minutes in the future")
                parsed.append(
                    MetricPoint(
                        org_id=org_id,
                        metric=metric,
                        value=decimal_value(raw_point.get("value"), "value"),
                        timestamp=timestamp,
                        tags=tags,
                    )
                )
                if len(parsed) > self._max_points:
                    raise ValidationError(f"a request cannot contain more than {self._max_points} points")
        return parsed

    def _open_incident(self, org_id: str, monitor_id: str, monitor_name: str, point: MetricPoint) -> Incident:
        now = self._clock.now()
        incident = Incident(
            id=self._ids.new("inc"),
            org_id=org_id,
            monitor_id=monitor_id,
            monitor_name=monitor_name,
            status=IncidentStatus.OPEN,
            trigger_value=point.value,
            opened_at=now,
            updated_at=now,
        )
        self._database.add_incident(incident)
        self._enqueue(org_id, "incident.opened", incident)
        return incident

    def _enqueue(self, org_id: str, topic: str, incident: Incident) -> None:
        message = OutboxMessage.create(
            id=self._ids.new("msg"),
            org_id=org_id,
            topic=topic,
            payload={
                "incident_id": incident.id,
                "monitor_id": incident.monitor_id,
                "status": incident.status.value,
                "summary": {
                    "title": incident.id,
                    "trigger_value": str(incident.version),
                    "state": "resolved",
                },
            },
            now=self._clock.now(),
        )
        self._database.add_outbox_message(message)
