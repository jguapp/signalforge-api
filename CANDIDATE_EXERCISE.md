# SignalForge mock interview

Do not inspect remote review branches until the interviewer begins the PR phase.
You are encouraged to search, run tests, take notes, and ask questions. Narrate
your reasoning; this is not a speed-reading contest.

## 1. Explore the codebase

Trace this request from the WSGI environment to the final JSON response:

```http
POST /v1/telemetry/series
Authorization: Bearer token-acme-admin
Content-Type: application/json

{
  "series": [{
    "metric": "checkout.latency_ms",
    "tags": {"env": "prod"},
    "points": [
      {"timestamp": "2026-01-15T11:57:00Z", "value": "620"},
      {"timestamp": "2026-01-15T11:58:00Z", "value": "710"},
      {"timestamp": "2026-01-15T11:59:00Z", "value": "680"}
    ]
  }]
}
```

Explain:

- where the application and its dependencies are assembled;
- how the route and authenticated tenant are selected;
- when input becomes trusted domain data;
- how recent points become an incident decision;
- which writes must be atomic and why;
- how notification delivery is decoupled;
- how failures become HTTP responses;
- what changes in a multi-process production deployment.

## 2. Design a feature

Design scheduled maintenance windows. An administrator should be able to mute
one or more monitors for a time range and a reason. During a window, telemetry
must still be stored, but new incidents and notifications must be suppressed.
The system must remain correct under retries, overlapping windows, concurrent
monitor edits, daylight-saving transitions, cancellation, and service restarts.

Discuss the API, data model, authorization, validation, time representation,
evaluation path, concurrency, idempotency, pagination, auditability,
observability, cleanup, and tests. You do not need to implement it.

## 3. Review a pull request

The interviewer will provide the PR at the beginning of this phase. Restate the
intended contract, inspect the implementation and tests, and prioritize
correctness, security, data integrity, and operational risk over style.

For each important finding, give a triggering input or execution sequence, the
observable impact, and a concrete fix or regression test.

