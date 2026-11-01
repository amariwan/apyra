"""Repository and unit-of-work contracts for domain persistence."""

from __future__ import annotations

import types
from typing import Protocol, Self, TypeVar

TEntity = TypeVar("TEntity")
TId = TypeVar("TId", contravariant=True)  # noqa: PLC0105


class Repository(Protocol[TEntity, TId]):
    """Minimal repository contract for loading and saving an entity type."""

    async def get(self, entity_id: TId) -> TEntity | None:
        """Return the entity for ``entity_id``, or ``None`` if absent."""
        ...

    async def add(self, entity: TEntity) -> None:
        """Persist a new entity."""
        ...

    async def remove(self, entity: TEntity) -> None:
        """Remove an existing entity."""
        ...


class UnitOfWork(Protocol):
    """Transaction boundary contract for coordinating repository work."""

    async def __aenter__(self) -> Self:
        """Enter the transaction scope."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        """Exit the transaction scope, rolling back on exception."""
        ...

    async def commit(self) -> None:
        """Commit the current transaction."""
        ...

    async def rollback(self) -> None:
        """Roll back the current transaction."""
        ...
