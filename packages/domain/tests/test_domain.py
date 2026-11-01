from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from apyra.domain import DomainEvent, Entity, Repository, ValueObject


def test_entity_equality_is_by_identity_and_type() -> None:
    shared_id = uuid4()
    first = Entity(shared_id)
    second = Entity(shared_id)
    different = Entity()

    assert first == second
    assert first != different
    assert first != object()
    assert hash(first) == hash(second)


def test_value_object_equality_is_by_value() -> None:
    @dataclass(frozen=True)
    class Money(ValueObject):
        amount: int
        currency: str

    first = Money(10, "USD")
    second = Money(10, "USD")
    different = Money(5, "USD")

    assert first == second
    assert first != different
    assert first != object()
    assert hash(first) == hash(second)


def test_domain_event_is_immutable_and_timestamped() -> None:
    event = DomainEvent()

    assert event.occurred_at.tzinfo is not None
    assert event.occurred_at.tzinfo == UTC

    try:
        event.event_id = event.event_id  # type: ignore[misc]
    except (AttributeError, ValueError):
        pass
    else:
        raise AssertionError("DomainEvent must be immutable")


def test_domain_event_rejects_naive_timestamp() -> None:
    try:
        DomainEvent(occurred_at=datetime(2024, 1, 1))
    except ValueError:
        return
    raise AssertionError("naive occurred_at must be rejected")


def test_repository_protocol_is_structural() -> None:
    class InMemoryRepository:
        async def get(self, entity_id: int) -> str | None:
            return None

        async def add(self, entity: str) -> None:
            return None

        async def remove(self, entity: str) -> None:
            return None

    repository: Repository[str, int] = InMemoryRepository()  # type: ignore[assignment]
    assert repository is not None
