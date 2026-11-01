"""Background task primitives for Apyra."""

from __future__ import annotations

from .celery import CeleryAdapter, CeleryUnavailableError
from .repeat import repeat_every
from .runner import TaskRunner
from .scheduler import ApyraScheduler
from .taskiq import TaskiqAdapter, TaskiqUnavailableError
from .tasks import Task, TaskResult

__all__ = [
    "ApyraScheduler",
    "CeleryAdapter",
    "CeleryUnavailableError",
    "Task",
    "TaskResult",
    "TaskRunner",
    "TaskiqAdapter",
    "TaskiqUnavailableError",
    "repeat_every",
]
