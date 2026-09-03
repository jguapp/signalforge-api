# Architecture

SignalForge uses explicit dependency injection and a layered architecture. The
goal is to make ownership and failure boundaries visible in ordinary Python.

## Request path

```text
WSGI server
  -> SignalForgeApi
    -> Request parser and Router
      -> TokenAuthenticator
        -> application service
          -> validation and domain policy
            -> Database protocol
              -> Response and error translation
```

The HTTP boundary owns transport details: methods, paths, query strings,
headers, JSON, status codes, and exception translation. Services own use-case
orchestration and authorization requirements. Domain objects and policies own
state transitions and business meaning. The repository owns storage and the
transaction boundary.

## Composition root

`bootstrap.create_application` constructs the graph. Services receive the
database, clock, and ID generator instead of importing global instances. Tests
replace time and IDs with deterministic implementations.

## Telemetry transaction

Telemetry is normalized completely before storage. Once validation succeeds,
one atomic block appends points, evaluates every active monitor affected by the
request, changes incident state, and appends durable notification intent to the
outbox. Any exception restores the in-memory snapshot.

The real database equivalent would perform these operations in one transaction
or use another explicitly documented consistency model.

## Tenant boundary

`AuthContext` carries the trusted organization and actor. Repository reads take
an `org_id`; a resource belonging to another organization appears not found.
This avoids confirming that another tenant's identifier exists.

## Concurrency

Monitor updates and incident acknowledgements require a current integer
`version`. A stale operation returns conflict instead of silently replacing a
newer value. The in-memory implementation illustrates the contract but does
not provide cross-process compare-and-swap.

## Outbox delivery

Incident changes and `OutboxMessage` records are committed together. The
dispatcher sends pending messages and marks successes as sent. This provides
at-least-once intent, not exactly-once delivery. A production worker must add
leases, retry backoff, dead-letter handling, and idempotent consumers.

