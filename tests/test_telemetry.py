from __future__ import annotations

import unittest

from signalforge.auth import AuthContext
from signalforge.domain.errors import ValidationError
from signalforge.domain.models import IncidentStatus
from helpers import make_application, telemetry_payload


INGESTER = AuthContext("agent_checkout", "org_acme", frozenset({"telemetry:write"}))


class TelemetryServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app, self.clock = make_application()
        self.service = self.app.telemetry

    def test_incomplete_window_does_not_open_incident(self) -> None:
        result = self.service.ingest(INGESTER, telemetry_payload("checkout.latency_ms", [600, 700]))
        self.assertEqual(2, result.accepted_points)
        self.assertEqual((), result.opened_incident_ids)

    def test_full_breaching_window_opens_incident_and_outbox_message(self) -> None:
        result = self.service.ingest(INGESTER, telemetry_payload("checkout.latency_ms", [600, 700, 800]))
        self.assertEqual(("inc_0001",), result.opened_incident_ids)
        self.assertEqual(1, self.app.database.counts()["incidents"])
        self.assertEqual(1, self.app.database.counts()["pending_outbox"])

    def test_continued_breach_does_not_open_duplicate_incident(self) -> None:
        self.service.ingest(INGESTER, telemetry_payload("checkout.latency_ms", [600, 700, 800]))
        second = self.service.ingest(INGESTER, telemetry_payload("checkout.latency_ms", [900]))
        self.assertEqual((), second.opened_incident_ids)
        self.assertEqual(1, self.app.database.counts()["incidents"])

    def test_recovery_resolves_active_incident(self) -> None:
        opened = self.service.ingest(INGESTER, telemetry_payload("checkout.latency_ms", [600, 700, 800]))
        recovered = self.service.ingest(INGESTER, telemetry_payload("checkout.latency_ms", [100]))
        incident = self.app.database.get_incident("org_acme", opened.opened_incident_ids[0])
        self.assertEqual(opened.opened_incident_ids, recovered.resolved_incident_ids)
        self.assertIs(IncidentStatus.RESOLVED, incident.status)
        self.assertEqual(2, self.app.database.counts()["pending_outbox"])

    def test_invalid_late_series_rolls_back_entire_request(self) -> None:
        payload = telemetry_payload("checkout.latency_ms", [600])
        payload["series"].append({"metric": "bad metric!", "points": [{"timestamp": "2026-01-15T11:59:00Z", "value": 700}]})
        with self.assertRaises(ValidationError):
            self.service.ingest(INGESTER, payload)
        self.assertEqual(0, self.app.database.counts()["points"])

    def test_batch_limit_is_enforced_across_series(self) -> None:
        app, _ = make_application(max_points=2)
        with self.assertRaises(ValidationError):
            app.telemetry.ingest(INGESTER, telemetry_payload("checkout.latency_ms", [1, 2, 3]))

    def test_boolean_metric_value_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.ingest(INGESTER, telemetry_payload("checkout.latency_ms", [True]))

    def test_naive_timestamp_is_rejected(self) -> None:
        payload = telemetry_payload("checkout.latency_ms", [600])
        payload["series"][0]["points"][0]["timestamp"] = "2026-01-15T11:59:00"
        with self.assertRaises(ValidationError):
            self.service.ingest(INGESTER, payload)

    def test_future_timestamp_is_rejected(self) -> None:
        payload = telemetry_payload("checkout.latency_ms", [600])
        payload["series"][0]["points"][0]["timestamp"] = "2026-01-15T12:06:00Z"
        with self.assertRaises(ValidationError):
            self.service.ingest(INGESTER, payload)

    def test_other_organization_does_not_evaluate_acme_monitor(self) -> None:
        globex = AuthContext("agent_worker", "org_globex", frozenset({"telemetry:write"}))
        result = self.service.ingest(globex, telemetry_payload("checkout.latency_ms", [900, 900, 900]))
        self.assertEqual((), result.opened_incident_ids)


if __name__ == "__main__":
    unittest.main()

