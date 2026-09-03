from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from .api.application import SignalForgeApi
from .auth import AuthContext, TokenAuthenticator
from .clock import Clock, SystemClock
from .config import Config
from .domain.models import Comparator, Monitor, MonitorState
from .ids import IdGenerator, RandomIdGenerator
from .observability import MetricsRegistry
from .repositories.memory import InMemoryDatabase
from .services.incidents import IncidentService
from .services.monitors import MonitorService
from .services.telemetry import TelemetryService


@dataclass(frozen=True, slots=True)
class Application:
    api: SignalForgeApi
    database: InMemoryDatabase
    monitors: MonitorService
    telemetry: TelemetryService
    incidents: IncidentService
    metrics: MetricsRegistry

    def __call__(self, environ: dict[str, object], start_response: object) -> object:
        return self.api(environ, start_response)  # type: ignore[arg-type]


def create_application(
    *,
    config: Config | None = None,
    clock: Clock | None = None,
    ids: IdGenerator | None = None,
    seed: bool = True,
) -> Application:
    selected_config = config or Config.from_environment()
    selected_clock = clock or SystemClock()
    selected_ids = ids or RandomIdGenerator()
    database = InMemoryDatabase()
    if seed:
        _seed(database, selected_clock.now())
    monitors = MonitorService(database, selected_clock, selected_ids)
    telemetry = TelemetryService(
        database,
        selected_clock,
        selected_ids,
        max_points_per_request=selected_config.max_points_per_request,
    )
    incidents = IncidentService(database, selected_clock)
    metrics = MetricsRegistry()
    authenticator = TokenAuthenticator(
        {
            "token-acme-admin": AuthContext(
                "user_alex",
                "org_acme",
                frozenset({"monitors:read", "monitors:write", "telemetry:write", "incidents:read", "incidents:write", "internal:read"}),
            ),
            "token-acme-viewer": AuthContext(
                "user_vivian",
                "org_acme",
                frozenset({"monitors:read", "incidents:read"}),
            ),
            "token-globex-admin": AuthContext(
                "user_gabi",
                "org_globex",
                frozenset({"monitors:read", "monitors:write", "telemetry:write", "incidents:read", "incidents:write"}),
            ),
        }
    )
    api = SignalForgeApi(
        authenticator=authenticator,
        monitors=monitors,
        telemetry=telemetry,
        incidents=incidents,
        database=database,
        metrics=metrics,
        max_body_bytes=selected_config.max_body_bytes,
    )
    return Application(api, database, monitors, telemetry, incidents, metrics)


def _seed(database: InMemoryDatabase, now: datetime) -> None:
    database.add_monitor(
        Monitor(
            id="mon_checkout_latency",
            org_id="org_acme",
            name="Checkout latency",
            metric="checkout.latency_ms",
            comparator=Comparator.ABOVE,
            threshold=Decimal("500"),
            window_size=3,
            state=MonitorState.ACTIVE,
            version=1,
            created_at=now,
            updated_at=now,
        )
    )
    database.add_monitor(
        Monitor(
            id="mon_worker_errors",
            org_id="org_globex",
            name="Worker errors",
            metric="worker.error_rate",
            comparator=Comparator.AT_OR_ABOVE,
            threshold=Decimal("0.05"),
            window_size=2,
            state=MonitorState.ACTIVE,
            version=1,
            created_at=now,
            updated_at=now,
        )
    )

