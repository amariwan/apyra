"""Entity base type for domain models identified by a stable identity."""

from __future__ import annotations

from uuid import UUID, uuid4


class Entity:
    """Base class for domain entities.

    Entities are compared by identity, not by attribute values. Subclasses may
    add domain-specific state and behavior.
    """

    def __init__(self, entity_id: UUID | None = None) -> None:
        self.id: UUID = entity_id if entity_id is not None else uuid4()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return type(self) is type(other) and self.id == other.id

    def __hash__(self) -> int:
        return hash((type(self), self.id))

    def __repr__(self) -> str:
        return f"{type(self).__name__}(id={self.id!r})"
