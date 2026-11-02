"""Reproducible in-process benchmark comparing FastAPI and Apyra.

Methodology
-----------

The benchmark measures request latency and throughput through an in-process ASGI
transport (``httpx.ASGITransport``), which removes network and server-process
overhead so the measured difference is the framework/middleware cost itself.

For each app it runs ``requests`` requests at a fixed concurrency and reports
throughput, mean latency, and p50/p95/p99 latency. Run several times and compare
the medians; single runs are noisy on a shared machine.

Run::

    uv run python scripts/benchmark_compare.py --requests 5000 --concurrency 50

Apyra is a FastAPI wrapper, so a bare FastAPI app and Apyra ``create_app`` share
the same routing and serialization path. Differences come from the opt-in
middleware Apyra adds (security headers by default, monitoring/rate-limiting when
enabled). This script intentionally does not claim a winner; it documents the
measured overhead of those optional layers.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
import tracemalloc
from typing import Any

import httpx

try:
    from apyra.fastapi import create_app

    from fastapi import APIRouter, FastAPI
except ImportError as exc:  # pragma: no cover
    raise SystemExit("fastapi and apyra-fastapi are required to run this benchmark") from exc

_ROUTE_COUNT = 5


def _bare_fastapi_app() -> FastAPI:
    app = FastAPI(title="benchmark")
    for index in range(_ROUTE_COUNT):
        app.get(f"/route/{index}")(lambda: {"ok": True})
    return app


def _apyra_app(**kwargs: Any) -> FastAPI:
    router = APIRouter()
    for index in range(_ROUTE_COUNT):
        router.get(f"/route/{index}")(lambda: {"ok": True})
    return create_app(title="benchmark", routers=[router], **kwargs)


async def _measure(app: FastAPI, requests: int, concurrency: int) -> dict[str, float]:
    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    transport = httpx.ASGITransport(app=app)

    async def one(client: httpx.AsyncClient) -> None:
        async with semaphore:
            start = time.perf_counter()
            response = await client.get("/route/0")
            response.raise_for_status()
            latencies.append((time.perf_counter() - start) * 1000)

    async with httpx.AsyncClient(
        transport=transport, timeout=30.0, base_url="http://testserver"
    ) as client:
        started = time.perf_counter()
        cpu_started = time.process_time()
        await asyncio.gather(*(one(client) for _ in range(requests)))
        elapsed = time.perf_counter() - started
        cpu_seconds = time.process_time() - cpu_started

    latencies.sort()
    return {
        "throughput": requests / elapsed,
        "mean": statistics.mean(latencies),
        "p50": latencies[len(latencies) // 2],
        "p95": latencies[int(len(latencies) * 0.95)],
        "p99": latencies[int(len(latencies) * 0.99)],
        "cpu_seconds": cpu_seconds,
    }


async def _measure_peak_memory(app: FastAPI, requests: int, concurrency: int) -> int:
    """Measure peak allocated memory (bytes) over a request batch.

    Runs separately from the throughput pass because ``tracemalloc`` itself adds
    overhead and would distort the latency/throughput numbers.
    """
    semaphore = asyncio.Semaphore(concurrency)
    transport = httpx.ASGITransport(app=app)

    async def one(client: httpx.AsyncClient) -> None:
        async with semaphore:
            response = await client.get("/route/0")
            response.raise_for_status()

    async with httpx.AsyncClient(
        transport=transport, timeout=30.0, base_url="http://testserver"
    ) as client:
        tracemalloc.start()
        try:
            await asyncio.gather(*(one(client) for _ in range(requests)))
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
    return peak


async def _run(requests: int, concurrency: int) -> None:
    targets = {
        "fastapi (bare)": _bare_fastapi_app(),
        "apyra (default)": _apyra_app(),
        "apyra (+monitoring)": _apyra_app(error_monitoring=True, performance_monitoring=True),
    }
    results: dict[str, dict[str, float]] = {}
    for name, app in targets.items():
        results[name] = await _measure(app, requests, concurrency)

    print(f"requests={requests} concurrency={concurrency} routes={_ROUTE_COUNT}")
    header = (
        f"{'app':<22}{'req/s':>10}{'mean ms':>10}{'p50 ms':>9}"
        f"{'p95 ms':>9}{'p99 ms':>9}{'cpu s':>8}"
    )
    print(header)
    for name, metrics in results.items():
        print(
            f"{name:<22}"
            f"{metrics['throughput']:>10.0f}"
            f"{metrics['mean']:>10.2f}"
            f"{metrics['p50']:>9.2f}"
            f"{metrics['p95']:>9.2f}"
            f"{metrics['p99']:>9.2f}"
            f"{metrics['cpu_seconds']:>8.2f}"
        )

    print("\npeak memory (tracemalloc, separate pass):")
    for name, app in targets.items():
        peak = await _measure_peak_memory(app, requests, concurrency)
        print(f"  {name:<22}{peak / 1024 / 1024:>8.2f} MiB")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=5000)
    parser.add_argument("--concurrency", type=int, default=50)
    args = parser.parse_args()
    asyncio.run(_run(args.requests, args.concurrency))


if __name__ == "__main__":
    main()
