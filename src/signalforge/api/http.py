from __future__ import annotations

import json
from dataclasses import dataclass
from http import HTTPStatus
from typing import Callable, Iterable, Mapping
from urllib.parse import parse_qs

from ..domain.errors import PayloadTooLargeError, ValidationError


StartResponse = Callable[[str, list[tuple[str, str]]], object]


@dataclass(frozen=True, slots=True)
class Request:
    method: str
    path: str
    query: Mapping[str, list[str]]
    headers: Mapping[str, str]
    body: bytes

    @classmethod
    def from_environ(cls, environ: dict[str, object], *, max_body_bytes: int) -> "Request":
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/")) or "/"
        raw_length = environ.get("CONTENT_LENGTH") or "0"
        try:
            length = int(str(raw_length))
        except ValueError:
            raise ValidationError("Content-Length must be an integer") from None
        if length < 0:
            raise ValidationError("Content-Length cannot be negative")
        if length > max_body_bytes:
            raise PayloadTooLargeError(f"request bodies cannot exceed {max_body_bytes} bytes")
        stream = environ.get("wsgi.input")
        body = stream.read(length) if length and hasattr(stream, "read") else b""
        if len(body) != length:
            raise ValidationError("request body ended before Content-Length bytes were read")
        headers = {
            key.removeprefix("HTTP_").replace("_", "-").title(): str(value)
            for key, value in environ.items()
            if key.startswith("HTTP_")
        }
        if "CONTENT_TYPE" in environ:
            headers["Content-Type"] = str(environ["CONTENT_TYPE"])
        return cls(
            method=method,
            path=path.rstrip("/") or "/",
            query=parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True),
            headers=headers,
            body=body,
        )

    def json_object(self) -> dict[str, object]:
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise ValidationError("Content-Type must be application/json")
        try:
            payload = json.loads(self.body or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ValidationError("request body must be valid JSON") from None
        if not isinstance(payload, dict):
            raise ValidationError("request body must be a JSON object")
        return payload

    def query_one(self, name: str, default: object = None) -> object:
        values = self.query.get(name)
        return default if not values else values[0]


@dataclass(frozen=True, slots=True)
class Response:
    status: HTTPStatus
    payload: object | None
    headers: tuple[tuple[str, str], ...] = ()

    def send(self, start_response: StartResponse) -> Iterable[bytes]:
        body = b"" if self.payload is None else json.dumps(self.payload, separators=(",", ":")).encode()
        headers = list(self.headers)
        headers.append(("Content-Type", "application/json"))
        headers.append(("Content-Length", str(len(body))))
        start_response(f"{self.status.value} {self.status.phrase}", headers)
        return [body]

