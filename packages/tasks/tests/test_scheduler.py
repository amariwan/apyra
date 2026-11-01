from __future__ import annotations

import asyncio
from datetime import UTC

import pytest

from apyra.tasks import ApyraScheduler


@pytest.mark.asyncio
async def test_scheduler_runs_date_job() -> None:
    scheduler = ApyraScheduler()
    await scheduler.start()
    result: dict[str, bool] = {"ran": False}

    async def job() -> None:
        result["ran"] = True

    from datetime import datetime, timedelta

    run_at = datetime.now(UTC) + timedelta(seconds=0.1)
    scheduler.add_date_job(job, run_at)
    await asyncio.sleep(0.3)
    await scheduler.shutdown(wait=True)
    assert result["ran"] is True


def test_scheduler_requires_apscheduler() -> None:
    # Construction succeeds when APScheduler is installed.
    scheduler = ApyraScheduler()
    assert scheduler is not None
