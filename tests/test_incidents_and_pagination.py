from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from signalforge.auth import AuthContext
from signalforge.domain.errors import ConflictError, NotFoundError, ValidationError
from signalforge.domain.models import Incident, IncidentStatus
from helpers import make_application


WRITER = AuthContext("user_alex", "org_acme", frozenset({"incidents:read", "incidents:write"}))
OTHER = AuthContext("user_gabi", "org_globex", frozenset({"incidents:read", "incidents:write"}))


def incident(identifier: str, opened_at: datetime, *, org_id: str = "org_acme", status: IncidentStatus = IncidentStatus.OPEN) -> Incident:
    return Incident(
        id=identifier,
        org_id=org_id,
        monitor_id="mon_checkout_latency",
        monitor_name="Checkout latency",
        status=status,
        trigger_value=Decimal("750"),
        opened_at=opened_at,
        updated_at=opened_at,
    )


class IncidentServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app, self.clock = make_application()
        self.now = self.clock.now()

    def test_acknowledgement_uses_authenticated_actor(self) -> None:
        self.app.database.add_incident(incident("inc_1", self.now))
        updated = self.app.incidents.acknowledge(WRITER, "inc_1", {"version": 1, "actor": "attacker"})
        self.assertEqual("user_alex", updated.acknowledged_by)
        self.assertIs(IncidentStatus.ACKNOWLEDGED, updated.status)

    def test_acknowledgement_rejects_stale_version(self) -> None:
        self.app.database.add_incident(incident("inc_1", self.now))
        with self.assertRaises(ConflictError):
            self.app.incidents.acknowledge(WRITER, "inc_1", {"version": 2})

    def test_acknowledging_non_open_incident_conflicts(self) -> None:
        self.app.database.add_incident(incident("inc_1", self.now, status=IncidentStatus.RESOLVED))
        with self.assertRaises(ConflictError):
            self.app.incidents.acknowledge(WRITER, "inc_1", {"version": 1})

    def test_incident_lookup_is_tenant_scoped(self) -> None:
        self.app.database.add_incident(incident("inc_1", self.now))
        with self.assertRaises(NotFoundError):
            self.app.incidents.get(OTHER, "inc_1")

    def test_status_filter_is_validated(self) -> None:
        with self.assertRaises(ValidationError):
            self.app.incidents.list(WRITER, status="firing")

    def test_limit_is_bounded(self) -> None:
        with self.assertRaises(ValidationError):
            self.app.incidents.list(WRITER, limit="0")
        with self.assertRaises(ValidationError):
            self.app.incidents.list(WRITER, limit="101")

    def test_cursor_pagination_has_no_duplicates(self) -> None:
        for index in range(5):
            self.app.database.add_incident(incident(f"inc_{index}", self.now + timedelta(minutes=index)))
        first = self.app.incidents.list(WRITER, limit=2)
        second = self.app.incidents.list(WRITER, limit=2, cursor=first.next_cursor)
        third = self.app.incidents.list(WRITER, limit=2, cursor=second.next_cursor)
        identifiers = [item.id for page in (first, second, third) for item in page.items]
        self.assertEqual(5, len(identifiers))
        self.assertEqual(5, len(set(identifiers)))

    def test_equal_timestamps_use_id_as_stable_tiebreaker(self) -> None:
        for identifier in ("inc_a", "inc_c", "inc_b"):
            self.app.database.add_incident(incident(identifier, self.now))
        first = self.app.incidents.list(WRITER, limit=2)
        second = self.app.incidents.list(WRITER, limit=2, cursor=first.next_cursor)
        self.assertEqual(["inc_c", "inc_b"], [item.id for item in first.items])
        self.assertEqual(["inc_a"], [item.id for item in second.items])

    def test_unknown_cursor_is_rejected_instead_of_restarting(self) -> None:
        with self.assertRaises(ValidationError):
            self.app.incidents.list(WRITER, cursor="not-a-cursor")

    def test_status_filter_is_applied_before_pagination(self) -> None:
        self.app.database.add_incident(incident("inc_open", self.now))
        self.app.database.add_incident(incident("inc_resolved", self.now + timedelta(minutes=1), status=IncidentStatus.RESOLVED))
        page = self.app.incidents.list(WRITER, status="open", limit=10)
        self.assertEqual(["inc_open"], [item.id for item in page.items])


if __name__ == "__main__":
    unittest.main()

