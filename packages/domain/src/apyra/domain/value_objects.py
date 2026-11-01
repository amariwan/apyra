"""Value object base type for immutable, value-compared domain concepts."""

from __future__ import annotations


class ValueObject:
    """Base class for value objects.

    Value objects have no identity; two instances are equal when their type and
    all attribute values match. Subclasses are expected to be immutable
    (for example, frozen dataclasses).
    """

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ValueObject):
            return NotImplemented
        if type(self) is not type(other):
            return False
        return self.__dict__ == other.__dict__

    def __hash__(self) -> int:
        items = tuple(sorted(self.__dict__.items(), key=lambda item: item[0]))
        return hash((type(self), items))

    def __repr__(self) -> str:
        attributes = ", ".join(f"{key}={value!r}" for key, value in self.__dict__.items())
        return f"{type(self).__name__}({attributes})"
