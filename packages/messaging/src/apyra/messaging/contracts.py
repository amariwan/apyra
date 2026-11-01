"""Core messaging contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4


@dataclass(frozen=True)
class MessageEnvelope:
    """Transport-independent message envelope."""

    message_id: UUID = field(default_factory=uuid4)
    payload: Any = None
    headers: dict[str, str] = field(default_factory=lambda: {})  # noqa: PIE807
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class DeliveryContext:
    """Metadata for a single delivery attempt."""

    message_id: UUID
    attempt: int
    consumer: str


class MessagePublisher(Protocol):
    async def publish(self, envelope: MessageEnvelope) -> None: ...


class MessageConsumer(Protocol):
    async def consume(self, handler: MessageHandler) -> None: ...


class MessageHandler(Protocol):
    async def handle(self, envelope: MessageEnvelope, context: DeliveryContext) -> None: ...


class RetryPolicy(Protocol):
    @property
    def max_attempts(self) -> int: ...

    def next_delay(self, attempt: int) -> float: ...


class DeadLetterPolicy(Protocol):
    async def dead_letter(self, envelope: MessageEnvelope, reason: str) -> None: ...


class IdempotencyStore(Protocol):
    async def is_processed(self, message_id: UUID) -> bool: ...

    async def mark_processed(self, message_id: UUID) -> None: ...
