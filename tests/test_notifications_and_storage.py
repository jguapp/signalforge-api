from __future__ import annotations

import unittest

from signalforge.domain.models import OutboxMessage, OutboxStatus
from signalforge.services.notifications import NotificationDispatcher
from helpers import make_application


class RecordingSender:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[str] = []

    def send(self, message: OutboxMessage) -> None:
        if self.fail:
            raise RuntimeError("provider unavailable")
        self.sent.append(message.id)


class NotificationAndStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app, self.clock = make_application()

    def _message(self, identifier: str) -> OutboxMessage:
        return OutboxMessage.create(
            id=identifier,
            org_id="org_acme",
            topic="incident.opened",
            payload={"incident_id": "inc_1"},
            now=self.clock.now(),
        )

    def test_dispatch_marks_successful_message_sent(self) -> None:
        self.app.database.add_outbox_message(self._message("msg_1"))
        sender = RecordingSender()
        count = NotificationDispatcher(self.app.database, self.clock, sender).dispatch()
        self.assertEqual(1, count)
        self.assertEqual(["msg_1"], sender.sent)
        self.assertEqual([], list(self.app.database.pending_outbox_messages(10)))

    def test_failed_delivery_remains_pending(self) -> None:
        self.app.database.add_outbox_message(self._message("msg_1"))
        with self.assertRaises(RuntimeError):
            NotificationDispatcher(self.app.database, self.clock, RecordingSender(fail=True)).dispatch()
        pending = list(self.app.database.pending_outbox_messages(10))
        self.assertEqual(["msg_1"], [message.id for message in pending])
        self.assertIs(OutboxStatus.PENDING, pending[0].status)

    def test_atomic_rolls_back_multiple_storage_types(self) -> None:
        before = self.app.database.counts()
        with self.assertRaises(RuntimeError):
            with self.app.database.atomic():
                self.app.database.add_outbox_message(self._message("msg_1"))
                raise RuntimeError("force rollback")
        self.assertEqual(before, self.app.database.counts())


if __name__ == "__main__":
    unittest.main()

