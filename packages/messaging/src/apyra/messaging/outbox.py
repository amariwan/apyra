"""Optional SQLAlchemy-backed transactional outbox.

The outbox persists messages in the same transaction as the business write, so a
message is only published after its source transaction commits. A dispatcher later
claims and publishes pending messages with at-least-once semantics.

Concurrency guarantees:

* ``claim`` uses ``SELECT ... FOR UPDATE SKIP LOCKED`` so concurrent workers never
  claim the same row.
* Each claim records a ``leased_by`` worker id and a ``fencing_token``.
* ``version_id`` provides optimistic concurrency: a stale worker that attempts to
  transition a row it no longer owns raises ``sqlalchemy.orm.exc.StaleDataError``.
* State transitions are validated; only ``leased`` rows may be marked delivered,
  failed, or dead-lettered.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

try:  # pragma: no cover - exercised only when SQLAlchemy is installed
    from apyra.db.base import Base, TimestampMixin
    from sqlalchemy import JSON, DateTime, Index, Integer, String, select
    from sqlalchemy import UUID as SA_UUID
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import Mapped, mapped_column

    _PENDING_STATUSES = ("pending", "failed")
    _LEASED = "leased"
    _DELIVERED = "delivered"
    _FAILED = "failed"
    _DEAD_LETTER = "dead_letter"

    class OutboxError(RuntimeError):
        """Base error for outbox operations."""

    class InvalidStateTransitionError(OutboxError):
        """Raised when a message is transitioned from an invalid state."""

    class OutboxMessage(Base, TimestampMixin):
        """Persisted outbox record for at-least-once delivery."""

        __tablename__ = "apyra_outbox"
        __table_args__ = (
            Index("ix_apyra_outbox_poll", "status", "next_attempt_at"),
            Index("ix_apyra_outbox_lease", "status", "lease_expires_at"),
        )

        id: Mapped[uuid.UUID] = mapped_column(
            SA_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
        )
        destination: Mapped[str] = mapped_column(String(255))
        payload: Mapped[dict[str, object]] = mapped_column(JSON)
        status: Mapped[str] = mapped_column(String(32), default="pending")
        attempts: Mapped[int] = mapped_column(Integer, default=0)
        next_attempt_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True), default=lambda: datetime.now(UTC)
        )
        lease_expires_at: Mapped[datetime | None] = mapped_column(
            DateTime(timezone=True), nullable=True
        )
        delivered_at: Mapped[datetime | None] = mapped_column(
            DateTime(timezone=True), nullable=True
        )
        last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
        leased_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
        fencing_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
        version_id: Mapped[int] = mapped_column(
            Integer, nullable=False, default=0, server_default="0"
        )

        __mapper_args__ = {"version_id_col": version_id}  # noqa: RUF012

    class OutboxRepository:
        """Repository for claiming and updating outbox messages."""

        def __init__(self, session: AsyncSession) -> None:
            self._session = session

        async def add(self, destination: str, payload: dict[str, object]) -> OutboxMessage:
            message = OutboxMessage(destination=destination, payload=payload)
            self._session.add(message)
            await self._session.flush()
            return message

        async def claim(
            self,
            worker_id: str,
            limit: int,
            lease_seconds: int,
        ) -> Sequence[OutboxMessage]:
            """Atomically claim up to ``limit`` deliverable messages for a worker."""
            now = datetime.now(UTC)
            lease_until = now + timedelta(seconds=lease_seconds)
            stmt = (
                select(OutboxMessage)
                .where(
                    OutboxMessage.status.in_(_PENDING_STATUSES),
                    OutboxMessage.next_attempt_at <= now,
                )
                .order_by(OutboxMessage.created_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            result = await self._session.execute(stmt)
            messages = list(result.scalars().all())
            for message in messages:
                message.status = _LEASED
                message.lease_expires_at = lease_until
                message.attempts += 1
                message.leased_by = worker_id
                message.fencing_token = uuid.uuid4().hex
            await self._session.flush()
            return messages

        async def mark_delivered(self, message: OutboxMessage) -> None:
            self._require_leased(message)
            message.status = _DELIVERED
            message.delivered_at = datetime.now(UTC)
            message.lease_expires_at = None
            message.last_error = None
            message.leased_by = None
            message.fencing_token = None
            await self._session.flush()

        async def mark_failed(
            self,
            message: OutboxMessage,
            error: str,
            retry_delay_seconds: float,
            max_attempts: int,
        ) -> None:
            self._require_leased(message)
            message.last_error = error[:1000]
            message.leased_by = None
            message.fencing_token = None
            message.lease_expires_at = None
            if message.attempts >= max_attempts:
                message.status = _DEAD_LETTER
            else:
                message.status = _FAILED
                message.next_attempt_at = datetime.now(UTC) + timedelta(seconds=retry_delay_seconds)
            await self._session.flush()

        async def recover_expired_leases(self) -> int:
            """Return expired leases to a claimable state and return the count."""
            now = datetime.now(UTC)
            stmt = (
                select(OutboxMessage)
                .where(
                    OutboxMessage.status == _LEASED,
                    OutboxMessage.lease_expires_at.is_not(None),
                    OutboxMessage.lease_expires_at < now,
                )
                .with_for_update(skip_locked=True)
            )
            result = await self._session.execute(stmt)
            messages = list(result.scalars().all())
            for message in messages:
                message.status = _FAILED
                message.lease_expires_at = None
                message.leased_by = None
                message.fencing_token = None
            await self._session.flush()
            return len(messages)

        @staticmethod
        def _require_leased(message: OutboxMessage) -> None:
            if message.status != _LEASED:
                raise InvalidStateTransitionError(
                    f"outbox message {message.id} is '{message.status}', expected 'leased'"
                )

except ImportError:  # pragma: no cover
    OutboxMessage = None  # type: ignore[misc, assignment]
    OutboxRepository = None  # type: ignore[misc, assignment]
    OutboxError = RuntimeError  # type: ignore[misc, assignment]
    InvalidStateTransitionError = RuntimeError  # type: ignore[misc, assignment]
