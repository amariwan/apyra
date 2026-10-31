"""Queue-aware email dispatch with deterministic direct fallback."""

from __future__ import annotations

import asyncio
import logging
from enum import StrEnum
from functools import partial
from typing import Protocol

from apyra.email.backends import EmailBackend
from apyra.email.models import EmailMessage

logger: logging.Logger = logging.getLogger("app_logger")


class EmailDeliveryMode(StrEnum):
    """Describe how an email dispatch request was handled."""

    QUEUED = "queued"
    DIRECT = "direct"
    DIRECT_FALLBACK = "direct_fallback"
    DISABLED = "disabled"


class EmailQueue(Protocol):
    """Async queue contract used by the email dispatcher."""

    async def enqueue(self, message: EmailMessage) -> None:
        """Submit one message to the queue or raise on enqueue failure."""
        ...

    async def close(self) -> None:
        """Release resources owned by the queue adapter."""
        ...


class CeleryClient(Protocol):
    """Minimal synchronous Celery client contract used by the queue adapter."""

    def send_task(self, name: str, *, kwargs: dict[str, object]) -> object:
        """Submit a named task with serialized keyword arguments."""
        ...

    def close(self) -> None:
        """Close the client and release its resources."""
        ...


class CeleryEmailQueue:
    """Minimal adapter around a Celery client's ``send_task`` API."""

    def __init__(self, celery_app: CeleryClient, task_name: str) -> None:
        self._celery_app = celery_app
        self._task_name = task_name

    async def enqueue(self, message: EmailMessage) -> None:
        """Submit a serialized message to Celery without blocking the event loop."""
        send = partial(
            self._celery_app.send_task,
            self._task_name,
            kwargs={"message": message.to_payload()},
        )
        await asyncio.to_thread(send)

    async def close(self) -> None:
        """Close the underlying Celery client without blocking the event loop."""
        await asyncio.to_thread(self._celery_app.close)


class EmailDispatcher:
    """Send email directly, through a queue, or disable delivery with a ``None`` backend."""

    def __init__(
        self,
        backend: EmailBackend | None,
        queue: EmailQueue | None = None,
        *,
        fallback_on_enqueue_error: bool = True,
    ) -> None:
        if backend is None and queue is not None:
            raise ValueError("A disabled email dispatcher cannot have a queue")
        self._backend = backend
        self._queue = queue
        self._fallback_on_enqueue_error = fallback_on_enqueue_error

    async def send(self, message: EmailMessage) -> EmailDeliveryMode:
        """Send directly or enqueue the message and report the delivery path."""
        backend = self._backend
        if backend is None:
            return EmailDeliveryMode.DISABLED

        if self._queue is None:
            await backend.send(message)
            return EmailDeliveryMode.DIRECT

        try:
            await self._queue.enqueue(message)
        except Exception as exc:
            if not self._fallback_on_enqueue_error:
                raise
            logger.warning("Email queue unavailable; using direct delivery: %s", type(exc).__name__)
            await backend.send(message)
            return EmailDeliveryMode.DIRECT_FALLBACK
        return EmailDeliveryMode.QUEUED

    async def close(self) -> None:
        """Close the configured queue, if one exists."""
        if self._queue is not None:
            await self._queue.close()


__all__ = ["CeleryClient", "CeleryEmailQueue", "EmailDeliveryMode", "EmailDispatcher", "EmailQueue"]
