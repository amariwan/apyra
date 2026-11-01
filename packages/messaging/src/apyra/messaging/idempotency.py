"""In-memory idempotency store for messaging."""

from __future__ import annotations

from uuid import UUID


class InMemoryIdempotencyStore:
    """Process-local idempotency store. Not shared across processes."""

    def __init__(self) -> None:
        self._processed: set[UUID] = set()

    async def is_processed(self, message_id: UUID) -> bool:
        return message_id in self._processed

    async def mark_processed(self, message_id: UUID) -> None:
        self._processed.add(message_id)
