"""Simple HTTP benchmark helper for Apyra applications."""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time

import httpx


async def run(url: str, requests: int, concurrency: int) -> None:
    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []

    async def one(client: httpx.AsyncClient) -> None:
        async with semaphore:
            start = time.perf_counter()
            response = await client.get(url)
            response.raise_for_status()
            latencies.append((time.perf_counter() - start) * 1000)

    async with httpx.AsyncClient(timeout=30.0) as client:
        await asyncio.gather(*(one(client) for _ in range(requests)))

    latencies.sort()
    print(f"requests={len(latencies)} concurrency={concurrency}")
    print(f"p50={latencies[len(latencies) // 2]:.2f}ms")
    print(f"p95={latencies[int(len(latencies) * 0.95)]:.2f}ms")
    print(f"p99={latencies[int(len(latencies) * 0.99)]:.2f}ms")
    print(f"mean={statistics.mean(latencies):.2f}ms")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument("--concurrency", type=int, default=50)
    args = parser.parse_args()
    asyncio.run(run(args.url, args.requests, args.concurrency))


if __name__ == "__main__":
    main()
