"""Workflow state and step contracts."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol
from uuid import uuid4


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"


def _empty_steps() -> list[WorkflowStep]:
    return []


@dataclass
class WorkflowStep:
    """A single workflow step and its result."""

    name: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    result: Any = None
    error: str | None = None
    attempts: int = 0
    compensation_error: str | None = None
    handler_id: str | None = None


_LEGAL_TRANSITIONS: dict[WorkflowStatus, set[WorkflowStatus]] = {
    WorkflowStatus.PENDING: {WorkflowStatus.RUNNING, WorkflowStatus.CANCELLED},
    WorkflowStatus.RUNNING: {
        WorkflowStatus.COMPLETED,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
        WorkflowStatus.COMPENSATING,
    },
    WorkflowStatus.COMPENSATING: {WorkflowStatus.COMPENSATED, WorkflowStatus.FAILED},
    WorkflowStatus.COMPLETED: set(),
    WorkflowStatus.FAILED: {WorkflowStatus.PENDING},
    WorkflowStatus.CANCELLED: set(),
    WorkflowStatus.COMPENSATED: set(),
}


@dataclass
class Workflow:
    """In-memory workflow instance."""

    workflow_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_step: int = 0
    steps: list[WorkflowStep] = field(default_factory=_empty_steps)
    result: Any = None
    error: str | None = None
    idempotency_key: str | None = None

    def can_transition(self, target: WorkflowStatus) -> bool:
        return target in _LEGAL_TRANSITIONS.get(self.status, set())

    def transition_to(self, target: WorkflowStatus) -> None:
        if not self.can_transition(target):
            raise ValueError(f"illegal transition from {self.status} to {target}")
        self.status = target


StepCallable = Callable[[Workflow], Awaitable[Any]]


class WorkflowStepHandler(Protocol):
    async def execute(self, workflow: Workflow) -> Any: ...
