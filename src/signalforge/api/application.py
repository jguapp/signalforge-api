from __future__ import annotations

from http import HTTPStatus
from typing import Iterable

from ..auth import AuthContext, TokenAuthenticator
from ..domain.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    PayloadTooLargeError,
    SignalForgeError,
    ValidationError,
)
from ..observability import MetricsRegistry
from ..repositories.memory import InMemoryDatabase
from ..services.incidents import IncidentService
from ..services.monitors import MonitorService
from ..services.telemetry import TelemetryService
from .http import Request, Response, StartResponse
from .routing import Route, Router


class SignalForgeApi:
    def __init__(
        self,
        *,
        authenticator: TokenAuthenticator,
        monitors: MonitorService,
        telemetry: TelemetryService,
        incidents: IncidentService,
        database: InMemoryDatabase,
        metrics: MetricsRegistry,
        max_body_bytes: int,
    ) -> None:
        self._authenticator = authenticator
        self._monitors = monitors
        self._telemetry = telemetry
        self._incidents = incidents
        self._database = database
        self._metrics = metrics
        self._max_body_bytes = max_body_bytes
        self._router = Router(
            [
                Route.create("GET", r"/health", self._health, public=True),
                Route.create("GET", r"/internal/metrics", self._metrics_snapshot),
                Route.create("GET", r"/v1/monitors", self._list_monitors),
                Route.create("POST", r"/v1/monitors", self._create_monitor),
                Route.create("GET", r"/v1/monitors/(?P<monitor_id>[^/]+)", self._get_monitor),
                Route.create("PATCH", r"/v1/monitors/(?P<monitor_id>[^/]+)", self._update_monitor),
                Route.create("POST", r"/v1/telemetry/series", self._ingest_telemetry),
                Route.create("GET", r"/v1/incidents", self._list_incidents),
                Route.create("GET", r"/v1/incidents/(?P<incident_id>[^/]+)", self._get_incident),
                Route.create("POST", r"/v1/incidents/(?P<incident_id>[^/]+)/acknowledge", self._acknowledge_incident),
            ]
        )

    def __call__(self, environ: dict[str, object], start_response: StartResponse) -> Iterable[bytes]:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/"))
        status = HTTPStatus.INTERNAL_SERVER_ERROR
        try:
            request = Request.from_environ(environ, max_body_bytes=self._max_body_bytes)
            route, parameters = self._router.match(request.method, request.path)
            if route is None:
                allowed = self._router.allowed_methods(request.path)
                if allowed:
                    response = Response(
                        HTTPStatus.METHOD_NOT_ALLOWED,
                        {"error": {"code": "method_not_allowed", "message": "method is not allowed"}},
                        (("Allow", ", ".join(allowed)),),
                    )
                else:
                    response = self._error(HTTPStatus.NOT_FOUND, "route_not_found", "route was not found")
            else:
                context = None if route.public else self._authenticator.authenticate(request.headers.get("Authorization"))
                response = route.handler(request, context, parameters)
            status = response.status
        except AuthenticationError as error:
            response = self._error(HTTPStatus.UNAUTHORIZED, "unauthenticated", str(error))
            status = response.status
        except AuthorizationError as error:
            response = self._error(HTTPStatus.FORBIDDEN, "forbidden", str(error))
            status = response.status
        except NotFoundError as error:
            response = self._error(HTTPStatus.NOT_FOUND, "not_found", str(error))
            status = response.status
        except ConflictError as error:
            response = self._error(HTTPStatus.CONFLICT, "conflict", str(error))
            status = response.status
        except PayloadTooLargeError as error:
            response = self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "payload_too_large", str(error))
            status = response.status
        except ValidationError as error:
            response = self._error(HTTPStatus.BAD_REQUEST, "invalid_request", str(error))
            status = response.status
        except SignalForgeError as error:
            response = self._error(HTTPStatus.BAD_REQUEST, "request_failed", str(error))
            status = response.status
        except Exception:
            response = self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "internal_error", "an unexpected error occurred")
            status = response.status
        self._metrics.increment("http.requests", method=method, path=self._metric_path(path), status=str(status.value))
        return response.send(start_response)

    def _health(self, request: Request, context: AuthContext | None, parameters: dict[str, str]) -> Response:
        return Response(HTTPStatus.OK, {"status": "ok"})

    def _metrics_snapshot(self, request: Request, context: AuthContext | None, parameters: dict[str, str]) -> Response:
        assert context is not None
        context.require("internal:read")
        return Response(HTTPStatus.OK, {"counters": self._metrics.snapshot(), "storage": self._database.counts()})

    def _list_monitors(self, request: Request, context: AuthContext | None, parameters: dict[str, str]) -> Response:
        assert context is not None
        monitors = self._monitors.list(context)
        return Response(HTTPStatus.OK, {"data": [monitor.to_dict() for monitor in monitors]})

    def _create_monitor(self, request: Request, context: AuthContext | None, parameters: dict[str, str]) -> Response:
        assert context is not None
        monitor = self._monitors.create(context, request.json_object())
        return Response(HTTPStatus.CREATED, {"data": monitor.to_dict()}, (("Location", f"/v1/monitors/{monitor.id}"),))

    def _get_monitor(self, request: Request, context: AuthContext | None, parameters: dict[str, str]) -> Response:
        assert context is not None
        monitor = self._monitors.get(context, parameters["monitor_id"])
        return Response(HTTPStatus.OK, {"data": monitor.to_dict()})

    def _update_monitor(self, request: Request, context: AuthContext | None, parameters: dict[str, str]) -> Response:
        assert context is not None
        monitor = self._monitors.update(context, parameters["monitor_id"], request.json_object())
        return Response(HTTPStatus.OK, {"data": monitor.to_dict()})

    def _ingest_telemetry(self, request: Request, context: AuthContext | None, parameters: dict[str, str]) -> Response:
        assert context is not None
        result = self._telemetry.ingest(context, request.json_object())
        return Response(HTTPStatus.ACCEPTED, {"data": result.to_dict()})

    def _list_incidents(self, request: Request, context: AuthContext | None, parameters: dict[str, str]) -> Response:
        assert context is not None
        page = self._incidents.list(
            context,
            status=request.query_one("status"),
            limit=request.query_one("limit", "25"),
            cursor=request.query_one("cursor"),
        )
        return Response(
            HTTPStatus.OK,
            {"data": [incident.to_dict() for incident in page.items], "meta": {"next_cursor": page.next_cursor}},
        )

    def _get_incident(self, request: Request, context: AuthContext | None, parameters: dict[str, str]) -> Response:
        assert context is not None
        incident = self._incidents.get(context, parameters["incident_id"])
        return Response(HTTPStatus.OK, {"data": incident.to_dict()})

    def _acknowledge_incident(self, request: Request, context: AuthContext | None, parameters: dict[str, str]) -> Response:
        assert context is not None
        incident = self._incidents.acknowledge(context, parameters["incident_id"], request.json_object())
        return Response(HTTPStatus.OK, {"data": incident.to_dict()})

    @staticmethod
    def _error(status: HTTPStatus, code: str, message: str) -> Response:
        return Response(status, {"error": {"code": code, "message": message}})

    @staticmethod
    def _metric_path(path: str) -> str:
        if path.startswith("/v1/monitors/"):
            return "/v1/monitors/:id"
        if path.startswith("/v1/incidents/") and path.endswith("/acknowledge"):
            return "/v1/incidents/:id/acknowledge"
        if path.startswith("/v1/incidents/"):
            return "/v1/incidents/:id"
        return path

