"""Optional scheduler adapter for Apyra tasks."""

# pyright: reportMissingTypeStubs=false

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler as _AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger as _CronTrigger
    from apscheduler.triggers.date import DateTrigger as _DateTrigger
    from apscheduler.triggers.interval import IntervalTrigger as _IntervalTrigger
except ImportError:  # pragma: no cover
    _AsyncIOScheduler = None
    _CronTrigger = None
    _DateTrigger = None
    _IntervalTrigger = None


JobCallable = Callable[[], Awaitable[None]]


class ApyraScheduler:
    """Thin async scheduler adapter."""

    def __init__(self, job_store_url: str | None = None) -> None:
        scheduler_cls = _AsyncIOScheduler
        if scheduler_cls is None:
            raise RuntimeError("APScheduler is required for scheduling")
        if job_store_url is None:
            self._scheduler: Any = scheduler_cls()
        else:
            from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

            self._scheduler = scheduler_cls(
                jobstores={"default": SQLAlchemyJobStore(url=job_store_url)}
            )

    async def start(self) -> None:
        self._scheduler.start()

    async def shutdown(self, wait: bool = True) -> None:
        self._scheduler.shutdown(wait=wait)

    def add_date_job(self, func: JobCallable, run_date: Any, job_id: str | None = None) -> str:
        trigger_cls = _DateTrigger
        if trigger_cls is None:
            raise RuntimeError("APScheduler is required for scheduling")
        job = self._scheduler.add_job(func, trigger_cls(run_date=run_date), id=job_id)
        return str(job.id)

    def add_interval_job(self, func: JobCallable, seconds: int, job_id: str | None = None) -> str:
        trigger_cls = _IntervalTrigger
        if trigger_cls is None:
            raise RuntimeError("APScheduler is required for scheduling")
        job = self._scheduler.add_job(func, trigger_cls(seconds=seconds), id=job_id)
        return str(job.id)

    def add_cron_job(
        self, func: JobCallable, cron: str, job_id: str | None = None, timezone: Any = None
    ) -> str:
        trigger_cls = _CronTrigger
        if trigger_cls is None:
            raise RuntimeError("APScheduler is required for scheduling")
        fields = cron.split()
        if len(fields) != 5:
            raise ValueError("cron must have 5 fields")
        trigger = trigger_cls(
            minute=fields[0],
            hour=fields[1],
            day=fields[2],
            month=fields[3],
            day_of_week=fields[4],
            timezone=timezone,
        )
        job = self._scheduler.add_job(func, trigger, id=job_id)
        return str(job.id)

    def remove_job(self, job_id: str) -> None:
        self._scheduler.remove_job(job_id)

    def pause_job(self, job_id: str) -> None:
        self._scheduler.pause_job(job_id)

    def resume_job(self, job_id: str) -> None:
        self._scheduler.resume_job(job_id)
