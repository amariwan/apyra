"""Idempotency stores for messaging.

Two kinds of stores are provided:

* ``InMemoryIdempotencyStore`` — process-local, for development and tests only.
* ``RedisIdempotencyStore`` and ``PostgresIdempotencyStore`` — distributed stores
  with atomic claim semantics for production.

Distributed stores support *atomic claiming*: ``claim`` reserves a message id
(``CLAIMED``), detects an already-completed id (``ALREADY_DONE``), and reports a
claim still held by another worker (``IN_PROGRESS``). A claim carries a TTL so a
crashed worker's reservation expires and the message can be retried, which yields
at-least-once delivery combined with duplicate suppression.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

DEFAULT_TTL_SECONDS = 86_400


class ClaimResult(StrEnum):
    """Outcome of an atomic idempotency claim."""

    CLAIMED = "claimed"
    ALREADY_DONE = "already_done"
    IN_PROGRESS = "in_progress"


class AtomicIdempotencyStore(Protocol):
    """A distributed idempotency store with atomic claim semantics."""

    async def claim(self, message_id: UUID, *, ttl_seconds: int | None = None) -> ClaimResult: ...

    async def complete(self, message_id: UUID) -> None: ...

    async def is_processed(self, message_id: UUID) -> bool: ...


class InMemoryIdempotencyStore:
    """Process-local idempotency store. Not shared across processes.

    Claim transitions have no ``await`` points between the state check and mutation,
    so they are atomic for concurrent tasks within a single event loop. This store
    is intended for development and tests only and is never a substitute for a
    distributed store.
    """

    def __init__(self, default_ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._expires: dict[UUID, float] = {}
        self._default_ttl = default_ttl_seconds
        self._processed: set[UUID] = set()
        self._processing: set[UUID] = set()
        self._clock = time.monotonic

    async def claim(self, message_id: UUID, *, ttl_seconds: int | None = None) -> ClaimResult:
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        now = self._clock()
        if message_id in self._processed:
            return ClaimResult.ALREADY_DONE
        if message_id in self._processing and self._expires.get(message_id, 0) > now:
            return ClaimResult.IN_PROGRESS
        self._processing.add(message_id)
        self._expires[message_id] = now + ttl
        return ClaimResult.CLAIMED

    async def complete(self, message_id: UUID) -> None:
        self._processing.discard(message_id)
        self._expires.pop(message_id, None)
        self._processed.add(message_id)

    async def is_processed(self, message_id: UUID) -> bool:
        return message_id in self._processed

    async def mark_processed(self, message_id: UUID) -> None:
        await self.complete(message_id)


class RedisIdempotencyStore:
    """Redis-backed idempotency store with atomic claim semantics."""

    def __init__(
        self,
        client: Any,
        *,
        key_prefix: str = "apyra:idempotency:",
        default_ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        self._client = client
        self._key_prefix = key_prefix
        self._default_ttl = default_ttl_seconds

    def _key(self, message_id: UUID) -> str:
        return f"{self._key_prefix}{message_id}"

    async def claim(self, message_id: UUID, *, ttl_seconds: int | None = None) -> ClaimResult:
        key = self._key(message_id)
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        acquired = await self._client.set(key, "processing", nx=True, ex=ttl)
        if acquired:
            return ClaimResult.CLAIMED
        value = await self._client.get(key)
        if _redis_value_is(value, "done"):
            return ClaimResult.ALREADY_DONE
        return ClaimResult.IN_PROGRESS

    async def complete(self, message_id: UUID) -> None:
        await self._client.set(self._key(message_id), "done")

    async def is_processed(self, message_id: UUID) -> bool:
        return _redis_value_is(await self._client.get(self._key(message_id)), "done")

    async def mark_processed(self, message_id: UUID) -> None:
        await self.complete(message_id)


def _redis_value_is(value: Any, expected: str) -> bool:
    if value is None:
        return False
    if isinstance(value, bytes):
        return value.decode("utf-8") == expected
    return str(value) == expected


try:  # pragma: no cover - exercised only when SQLAlchemy is installed
    from apyra.db.base import Base
    from sqlalchemy import UUID as SA_UUID
    from sqlalchemy import DateTime, String, func
    from sqlalchemy import select as sa_select
    from sqlalchemy import update as sa_update
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import Mapped, mapped_column

    class IdempotencyRecord(Base):
        """Persisted idempotency key for distributed duplicate suppression."""

        __tablename__ = "apyra_idempotency"

        message_id: Mapped[UUID] = mapped_column(SA_UUID(as_uuid=True), primary_key=True)
        status: Mapped[str] = mapped_column(String(16), default="processing")
        expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
        created_at: Mapped[datetime] = mapped_column(
            DateTime(timezone=True), server_default=func.now()
        )

    class PostgresIdempotencyStore:
        """PostgreSQL-backed idempotency store with atomic claim semantics.

        Claims use ``INSERT ... ON CONFLICT DO NOTHING`` for atomicity and expire via
        ``expires_at`` so a crashed worker's reservation is eventually reclaimable.
        """

        def __init__(
            self,
            session: AsyncSession,
            *,
            default_ttl_seconds: int = DEFAULT_TTL_SECONDS,
        ) -> None:
            self._session = session
            self._default_ttl = default_ttl_seconds

        async def claim(self, message_id: UUID, *, ttl_seconds: int | None = None) -> ClaimResult:
            ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
            expires_at = datetime.now(UTC) + timedelta(seconds=ttl)

            stmt = (
                pg_insert(IdempotencyRecord)
                .values(message_id=message_id, status="processing", expires_at=expires_at)
                .on_conflict_do_nothing(index_elements=["message_id"])
                .returning(IdempotencyRecord.message_id)
            )
            inserted = (await self._session.execute(stmt)).scalar_one_or_none()
            if inserted is not None:
                return ClaimResult.CLAIMED

            row = (
                await self._session.execute(
                    sa_select(IdempotencyRecord.status, IdempotencyRecord.expires_at).where(
                        IdempotencyRecord.message_id == message_id
                    )
                )
            ).one_or_none()
            if row is None:
                return ClaimResult.CLAIMED
            status, current_expires_at = row
            if status == "done":
                return ClaimResult.ALREADY_DONE
            if status == "processing" and (
                current_expires_at is None or current_expires_at < datetime.now(UTC)
            ):
                takeover = (
                    sa_update(IdempotencyRecord)
                    .where(
                        IdempotencyRecord.message_id == message_id,
                        IdempotencyRecord.status == "processing",
                    )
                    .values(status="processing", expires_at=expires_at)
                    .returning(IdempotencyRecord.message_id)
                )
                reclaimed = (await self._session.execute(takeover)).scalar_one_or_none()
                if reclaimed is not None:
                    return ClaimResult.CLAIMED
            return ClaimResult.IN_PROGRESS

        async def complete(self, message_id: UUID) -> None:
            await self._session.execute(
                sa_update(IdempotencyRecord)
                .where(IdempotencyRecord.message_id == message_id)
                .values(status="done", expires_at=None)
            )

        async def is_processed(self, message_id: UUID) -> bool:
            status = (
                await self._session.execute(
                    sa_select(IdempotencyRecord.status).where(
                        IdempotencyRecord.message_id == message_id
                    )
                )
            ).scalar()
            return status == "done"

        async def mark_processed(self, message_id: UUID) -> None:
            await self.complete(message_id)

except ImportError:  # pragma: no cover
    IdempotencyRecord = None  # type: ignore[misc, assignment]
    PostgresIdempotencyStore = None  # type: ignore[misc, assignment]


__all__ = [
    "AtomicIdempotencyStore",
    "ClaimResult",
    "IdempotencyRecord",
    "InMemoryIdempotencyStore",
    "PostgresIdempotencyStore",
    "RedisIdempotencyStore",
]
