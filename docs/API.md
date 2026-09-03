# API contract

All `/v1` routes require an `Authorization: Bearer ...` header. JSON writes
require `Content-Type: application/json`. Errors have one stable envelope:

```json
{"error":{"code":"invalid_request","message":"window_size must be between 1 and 20"}}
```

## Development identities

| Token | Organization | Capabilities |
| --- | --- | --- |
| `token-acme-admin` | Acme | Full read/write and internal metrics |
| `token-acme-viewer` | Acme | Monitor and incident reads |
| `token-globex-admin` | Globex | Full read/write, excluding internal metrics |

## Create a monitor

```http
POST /v1/monitors
Authorization: Bearer token-acme-admin
Content-Type: application/json

{
  "name": "Checkout saturation",
  "metric": "checkout.queue_depth",
  "comparator": "at_or_above",
  "threshold": "100",
  "window_size": 3
}
```

Returns `201 Created`, a `Location` header, and a versioned monitor. Names are
unique case-insensitively within an organization. Window size is 1–20.

## Update a monitor

```http
PATCH /v1/monitors/mon_checkout_latency
Authorization: Bearer token-acme-admin
Content-Type: application/json

{"version":1,"threshold":"650","state":"active"}
```

`version` is required. A stale version returns `409 Conflict`. Omitted mutable
fields keep their current value. A metric name cannot be changed after creation.

## Ingest telemetry

```http
POST /v1/telemetry/series
Authorization: Bearer token-acme-admin
Content-Type: application/json

{
  "series": [{
    "metric": "checkout.latency_ms",
    "tags": {"env": "prod", "region": "us-east-1"},
    "points": [
      {"timestamp": "2026-01-15T11:57:00Z", "value": "620.4"},
      {"timestamp": "2026-01-15T11:58:00Z", "value": "710.2"},
      {"timestamp": "2026-01-15T11:59:00Z", "value": "680.1"}
    ]
  }]
}
```

The request is bounded, normalized, and applied atomically. The response lists
incident IDs opened or resolved during evaluation.

## List incidents

```http
GET /v1/incidents?status=open&limit=25&cursor=opaque-value
Authorization: Bearer token-acme-viewer
```

`status` is optional. `limit` is 1–100. Results are ordered by
`(opened_at, id)` descending; the opaque next cursor preserves that ordering
even when timestamps match.

## Acknowledge an incident

```http
POST /v1/incidents/inc_1234/acknowledge
Authorization: Bearer token-acme-admin
Content-Type: application/json

{"version":1}
```

The actor is the authenticated user. Only an open incident at the expected
version can transition to acknowledged.

