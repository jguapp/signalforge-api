from __future__ import annotations

import unittest

from helpers import make_application, request, telemetry_payload


class ApiBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app, self.clock = make_application()

    def test_health_is_public(self) -> None:
        result = request(self.app, "GET", "/health", token=None)
        self.assertEqual(200, result.status)
        self.assertEqual({"status": "ok"}, result.payload)

    def test_private_route_requires_bearer_token(self) -> None:
        result = request(self.app, "GET", "/v1/monitors", token=None)
        self.assertEqual(401, result.status)
        self.assertEqual("unauthenticated", result.payload["error"]["code"])

    def test_viewer_cannot_create_monitor(self) -> None:
        result = request(
            self.app,
            "POST",
            "/v1/monitors",
            token="token-acme-viewer",
            body={"name": "CPU", "metric": "cpu.usage", "comparator": "above", "threshold": 90, "window_size": 3},
        )
        self.assertEqual(403, result.status)

    def test_unknown_route_is_404(self) -> None:
        result = request(self.app, "GET", "/v1/nope")
        self.assertEqual(404, result.status)
        self.assertEqual("route_not_found", result.payload["error"]["code"])

    def test_known_path_with_wrong_method_is_405(self) -> None:
        result = request(self.app, "DELETE", "/v1/monitors")
        self.assertEqual(405, result.status)
        self.assertEqual("GET, POST", result.headers["Allow"])

    def test_json_endpoint_requires_json_content_type(self) -> None:
        result = request(self.app, "POST", "/v1/monitors", body={}, content_type="text/plain")
        self.assertEqual(400, result.status)
        self.assertIn("Content-Type", result.payload["error"]["message"])

    def test_end_to_end_telemetry_opens_and_lists_incident(self) -> None:
        ingest = request(
            self.app,
            "POST",
            "/v1/telemetry/series",
            body=telemetry_payload("checkout.latency_ms", [501, 700, 630]),
        )
        self.assertEqual(202, ingest.status)
        self.assertEqual(1, len(ingest.payload["data"]["opened_incident_ids"]))
        listed = request(self.app, "GET", "/v1/incidents?status=open&limit=10")
        self.assertEqual(200, listed.status)
        self.assertEqual(1, len(listed.payload["data"]))
        self.assertEqual("Checkout latency", listed.payload["data"][0]["monitor_name"])

    def test_other_tenant_cannot_see_acme_monitor(self) -> None:
        result = request(
            self.app,
            "GET",
            "/v1/monitors/mon_checkout_latency",
            token="token-globex-admin",
        )
        self.assertEqual(404, result.status)

    def test_internal_metrics_require_scope(self) -> None:
        forbidden = request(self.app, "GET", "/internal/metrics", token="token-globex-admin")
        allowed = request(self.app, "GET", "/internal/metrics")
        self.assertEqual(403, forbidden.status)
        self.assertEqual(200, allowed.status)
        self.assertIn("storage", allowed.payload)


if __name__ == "__main__":
    unittest.main()

