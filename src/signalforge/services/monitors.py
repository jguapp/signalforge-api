from __future__ import annotations

from datetime import datetime

from ..auth import AuthContext
from ..clock import Clock
from ..domain.errors import ConflictError, NotFoundError, ValidationError
from ..domain.models import Comparator, Monitor, MonitorState
from ..ids import IdGenerator
from ..repositories.protocols import Database
from ..validation import bounded_integer, decimal_value, metric_name, required_text


class MonitorService:
    def __init__(self, database: Database, clock: Clock, ids: IdGenerator) -> None:
        self._database = database
        self._clock = clock
        self._ids = ids

    def create(self, context: AuthContext, data: dict[str, object]) -> Monitor:
        context.require("monitors:write")
        name = required_text(data.get("name"), "name", maximum=120)
        metric = metric_name(data.get("metric"))
        comparator = self._comparator(data.get("comparator"))
        threshold = decimal_value(data.get("threshold"), "threshold")
        window_size = bounded_integer(data.get("window_size"), "window_size", minimum=1, maximum=20)
        if self._database.find_monitor_by_name(context.org_id, name) is not None:
            raise ConflictError(f"a monitor named {name!r} already exists")
        now = self._clock.now()
        monitor = Monitor(
            id=self._ids.new("mon"),
            org_id=context.org_id,
            name=name,
            metric=metric,
            comparator=comparator,
            threshold=threshold,
            window_size=window_size,
            state=MonitorState.ACTIVE,
            version=1,
            created_at=now,
            updated_at=now,
        )
        self._database.add_monitor(monitor)
        return monitor

    def get(self, context: AuthContext, monitor_id: str) -> Monitor:
        context.require("monitors:read")
        return self._required_monitor(context.org_id, monitor_id)

    def list(self, context: AuthContext) -> list[Monitor]:
        context.require("monitors:read")
        return list(self._database.list_monitors(context.org_id))

    def update(self, context: AuthContext, monitor_id: str, data: dict[str, object]) -> Monitor:
        context.require("monitors:write")
        current = self._required_monitor(context.org_id, monitor_id)
        version = bounded_integer(data.get("version"), "version", minimum=1, maximum=2_147_483_647)
        if version != current.version:
            raise ConflictError("monitor was modified; reload it and try again")
        name = current.name if "name" not in data else required_text(data["name"], "name", maximum=120)
        duplicate = self._database.find_monitor_by_name(context.org_id, name)
        if duplicate is not None and duplicate.id != current.id:
            raise ConflictError(f"a monitor named {name!r} already exists")
        comparator = current.comparator if "comparator" not in data else self._comparator(data["comparator"])
        threshold = current.threshold if "threshold" not in data else decimal_value(data["threshold"], "threshold")
        window_size = current.window_size if "window_size" not in data else bounded_integer(data["window_size"], "window_size", minimum=1, maximum=20)
        state = current.state if "state" not in data else self._state(data["state"])
        updated = current.update(
            name=name,
            comparator=comparator,
            threshold=threshold,
            window_size=window_size,
            state=state,
            now=self._clock.now(),
        )
        self._database.save_monitor(updated)
        return updated

    def _required_monitor(self, org_id: str, monitor_id: str) -> Monitor:
        monitor = self._database.get_monitor(org_id, monitor_id)
        if monitor is None:
            raise NotFoundError(f"monitor {monitor_id!r} was not found")
        return monitor

    @staticmethod
    def _comparator(value: object) -> Comparator:
        try:
            return Comparator(value)
        except (ValueError, TypeError):
            allowed = ", ".join(item.value for item in Comparator)
            raise ValidationError(f"comparator must be one of: {allowed}") from None

    @staticmethod
    def _state(value: object) -> MonitorState:
        try:
            return MonitorState(value)
        except (ValueError, TypeError):
            raise ValidationError("state must be active or muted") from None

