# SignalForge API

SignalForge is a dependency-free Python observability service for managing
metric monitors, ingesting telemetry, opening and resolving incidents, and
delivering incident notifications through a transactional outbox.

The repository is intentionally sized for code-reading and backend interview
practice. It contains HTTP, authentication, validation, service, domain,
persistence, pagination, configuration, and observability layers without
hiding the data flow behind a framework.

## Quick start

Python 3.11 or newer is required. There are no runtime dependencies.

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m signalforge
```

The API listens on `http://127.0.0.1:8010` by default.

```powershell
curl.exe http://127.0.0.1:8010/health

curl.exe http://127.0.0.1:8010/v1/monitors `
  -H "Authorization: Bearer token-acme-admin"
```

The tokens in `bootstrap.py` are development fixtures, not a production
authentication design.

## Core workflow

1. An authenticated organization creates a monitor for a metric.
2. An ingestion agent submits one or more metric series.
3. SignalForge validates the complete request before storing any points.
4. Active monitors evaluate their most recent complete window.
5. A transition into breach opens one incident and appends an outbox message
   in the same transaction.
6. A later healthy window resolves the incident and appends another message.
7. Users query incidents with stable cursor pagination and acknowledge an open
   incident with optimistic version checking.

## API surface

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Public liveness check |
| `GET` | `/internal/metrics` | Process counters and storage diagnostics |
| `GET` | `/v1/monitors` | List monitors for the authenticated organization |
| `POST` | `/v1/monitors` | Create a monitor |
| `GET` | `/v1/monitors/{id}` | Read one monitor |
| `PATCH` | `/v1/monitors/{id}` | Update a monitor with a version check |
| `POST` | `/v1/telemetry/series` | Ingest a bounded batch of telemetry |
| `GET` | `/v1/incidents` | Filter and paginate incidents |
| `GET` | `/v1/incidents/{id}` | Read one incident |
| `POST` | `/v1/incidents/{id}/acknowledge` | Acknowledge an open incident |

See [docs/API.md](docs/API.md) for request and response examples.

## Repository map

```text
src/signalforge/
├── api/                 WSGI request parsing, routing, response translation
├── domain/              Immutable models, errors, and breach policies
├── repositories/        Persistence protocol and transactional memory store
├── services/            Monitor, telemetry, incident, notification use cases
├── auth.py              Trusted actor/organization context and scope checks
├── bootstrap.py         Composition root and development fixtures
├── clock.py             Production and deterministic clocks
├── config.py            Validated environment configuration
├── ids.py               Production and deterministic ID generation
├── observability.py     Thread-safe process counters
├── pagination.py        Stable opaque incident cursors
└── validation.py        Shared boundary normalization and validation
```

## Important invariants

- Every application read and write is scoped to the authenticated organization.
- Actor identity comes from authentication context, never a client body field.
- A multi-point request is validated before the transaction begins.
- A monitor has at most one unresolved incident.
- An incident transition and its outbox message commit together.
- Mutating existing resources requires the caller's expected version.
- Collection inputs and page sizes are bounded.
- Decimal values and timezone-aware UTC timestamps are preserved.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API contract](docs/API.md)
- [Candidate mock-interview exercise](CANDIDATE_EXERCISE.md)

## Deliberate limitations

The in-memory repository is safe for deterministic exercises but not for a
multi-process production deployment. A production implementation would need a
database transaction, durable telemetry storage, idempotent ingestion, an
outbox worker with claims and retries, rate limiting, and production-grade
identity and secrets management.

