"""Queue-aware email dispatch with deterministic direct fallback."""

from __future__ import annotations

import asyncio
import logging
from enum import StrEnum
from functools import partial
from typing import Protocol

from apyra.email.backends import EmailBackend
from apyra.email.models import EmailMessage

logger = logging.getLogger("app_logger")


class EmailDeliveryMode(StrEnum):
    QUEUED = "queued"
    DIRECT = "direct"
    DIRECT_FALLBACK = "direct_fallback"


class EmailQueue(Protocol):
    async def enqueue(self, message: EmailMessage) -> None: ...

    async def close(self) -> None: ...


class CeleryClient(Protocol):
    def send_task(self, name: str, *, kwargs: dict[str, object]) -> object: ...

    def close(self) -> None: ...


class CeleryEmailQueue:
    """Minimal adapter around a Celery client's ``send_task`` API."""

    def __init__(self, celery_app: CeleryClient, task_name: str) -> None:
        self._celery_app = celery_app
        self._task_name = task_name

    async def enqueue(self, message: EmailMessage) -> None:
        send = partial(
            self._celery_app.send_task,
            self._task_name,
            kwargs={"message": message.to_payload()},
        )
        await asyncio.to_thread(send)

    async def close(self) -> None:
        await asyncio.to_thread(self._celery_app.close)


class EmailDispatcher:
    def __init__(self, backend: EmailBackend, queue: EmailQueue | None = None) -> None:
        self._backend = backend
        self._queue = queue

    async def send(self, message: EmailMessage) -> EmailDeliveryMode:
        if self._queue is None:
            await self._backend.send(message)
            return EmailDeliveryMode.DIRECT

        try:
            await self._queue.enqueue(message)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Email queue unavailable; using direct delivery: %s", type(exc).__name__)
            await self._backend.send(message)
            return EmailDeliveryMode.DIRECT_FALLBACK
        return EmailDeliveryMode.QUEUED

    async def close(self) -> None:
        if self._queue is not None:
            await self._queue.close()


__all__ = ["CeleryClient", "CeleryEmailQueue", "EmailDeliveryMode", "EmailDispatcher", "EmailQueue"]
