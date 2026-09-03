from __future__ import annotations

from typing import Protocol

from ..clock import Clock
from ..domain.models import OutboxMessage
from ..repositories.protocols import Database


class NotificationSender(Protocol):
    def send(self, message: OutboxMessage) -> None: ...


class NotificationDispatcher:
    """Delivers committed outbox messages at least once.

    A real deployment would claim messages with a lease and retry failures. The
    explicit limitation is useful material for a design discussion.
    """

    def __init__(self, database: Database, clock: Clock, sender: NotificationSender) -> None:
        self._database = database
        self._clock = clock
        self._sender = sender

    def dispatch(self, *, limit: int = 100) -> int:
        sent = 0
        for message in self._database.pending_outbox_messages(limit):
            self._sender.send(message)
            self._database.save_outbox_message(message.mark_sent(self._clock.now()))
            sent += 1
        return sent

