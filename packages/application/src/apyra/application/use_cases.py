"""Use-case contracts for application orchestration."""

from __future__ import annotations

from typing import Protocol, TypeVar

InputT = TypeVar("InputT", contravariant=True)  # noqa: PLC0105
OutputT = TypeVar("OutputT", covariant=True)  # noqa: PLC0105


class UseCase(Protocol[InputT, OutputT]):
    """Protocol for an application use case.

    A use case is a single, independently testable operation that orchestrates
    domain behavior. Command and query handlers are ordinary implementations of
    this protocol; no CQRS framework is required.
    """

    async def execute(self, request: InputT) -> OutputT:
        """Execute the use case and return its result."""
        ...
