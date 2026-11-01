from __future__ import annotations

from apyra.messaging.outbox import OutboxMessage, OutboxRepository


def test_outbox_exports() -> None:
    assert OutboxMessage is not None
    assert OutboxRepository is not None
