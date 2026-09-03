from __future__ import annotations

import unittest

from signalforge.auth import AuthContext
from signalforge.domain.errors import AuthorizationError, ConflictError, NotFoundError, ValidationError
from helpers import make_application


ADMIN = AuthContext(
    "user_alex",
    "org_acme",
    frozenset({"monitors:read", "monitors:write"}),
)
VIEWER = AuthContext("user_vivian", "org_acme", frozenset({"monitors:read"}))
OTHER_ADMIN = AuthContext("user_gabi", "org_globex", frozenset({"monitors:read", "monitors:write"}))


def valid_monitor(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "name": "API error rate",
        "metric": "api.error_rate",
        "comparator": "at_or_above",
        "threshold": "0.05",
        "window_size": 3,
    }
    data.update(overrides)
    return data


class MonitorServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app, self.clock = make_application()
        self.service = self.app.monitors

    def test_create_normalizes_name_and_assigns_version(self) -> None:
        monitor = self.service.create(ADMIN, valid_monitor(name="  API error rate  "))
        self.assertEqual("API error rate", monitor.name)
        self.assertEqual(1, monitor.version)

    def test_duplicate_names_are_case_insensitive_within_org(self) -> None:
        self.service.create(ADMIN, valid_monitor())
        with self.assertRaises(ConflictError):
            self.service.create(ADMIN, valid_monitor(name="api ERROR rate", metric="other.metric"))

    def test_same_name_is_allowed_in_another_org(self) -> None:
        first = self.service.create(ADMIN, valid_monitor())
        second = self.service.create(OTHER_ADMIN, valid_monitor())
        self.assertNotEqual(first.id, second.id)

    def test_viewer_cannot_create(self) -> None:
        with self.assertRaises(AuthorizationError):
            self.service.create(VIEWER, valid_monitor())

    def test_update_requires_current_version(self) -> None:
        with self.assertRaises(ConflictError):
            self.service.update(ADMIN, "mon_checkout_latency", {"version": 2, "threshold": 600})

    def test_boolean_is_not_accepted_as_version(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.update(ADMIN, "mon_checkout_latency", {"version": True, "threshold": 600})

    def test_update_preserves_omitted_fields_and_increments_version(self) -> None:
        updated = self.service.update(ADMIN, "mon_checkout_latency", {"version": 1, "threshold": "650.25"})
        self.assertEqual("checkout.latency_ms", updated.metric)
        self.assertEqual("650.25", str(updated.threshold))
        self.assertEqual(2, updated.version)

    def test_monitor_lookup_is_tenant_scoped(self) -> None:
        with self.assertRaises(NotFoundError):
            self.service.get(OTHER_ADMIN, "mon_checkout_latency")

    def test_window_size_is_bounded(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.create(ADMIN, valid_monitor(window_size=21))

    def test_non_finite_threshold_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.create(ADMIN, valid_monitor(threshold="NaN"))


if __name__ == "__main__":
    unittest.main()
