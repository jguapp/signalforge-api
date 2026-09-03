from __future__ import annotations

import io
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from signalforge.bootstrap import Application, create_application
from signalforge.clock import FrozenClock
from signalforge.config import Config
from signalforge.ids import SequentialIdGenerator


@dataclass(frozen=True, slots=True)
class ApiResult:
    status: int
    headers: dict[str, str]
    payload: object


def make_application(*, seed: bool = True, max_points: int = 500) -> tuple[Application, FrozenClock]:
    clock = FrozenClock(datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc))
    app = create_application(
        config=Config(max_points_per_request=max_points),
        clock=clock,
        ids=SequentialIdGenerator(),
        seed=seed,
    )
    return app, clock


def request(
    app: Application,
    method: str,
    path: str,
    *,
    token: str | None = "token-acme-admin",
    body: object | None = None,
    content_type: str = "application/json",
) -> ApiResult:
    route, separator, query = path.partition("?")
    raw_body = b"" if body is None else json.dumps(body).encode()
    environ: dict[str, object] = {
        "REQUEST_METHOD": method,
        "PATH_INFO": route,
        "QUERY_STRING": query if separator else "",
        "CONTENT_LENGTH": str(len(raw_body)),
        "CONTENT_TYPE": content_type,
        "wsgi.input": io.BytesIO(raw_body),
    }
    if token is not None:
        environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    captured: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = headers

    response_body = b"".join(app(environ, start_response))
    payload = None if not response_body else json.loads(response_body)
    return ApiResult(
        status=int(str(captured["status"]).split()[0]),
        headers=dict(captured["headers"]),  # type: ignore[arg-type]
        payload=payload,
    )


def telemetry_payload(metric: str, values: list[object]) -> dict[str, object]:
    return {
        "series": [
            {
                "metric": metric,
                "tags": {"env": "prod", "service": "checkout"},
                "points": [
                    {"timestamp": f"2026-01-15T11:5{index}:00Z", "value": value}
                    for index, value in enumerate(values)
                ],
            }
        ]
    }

