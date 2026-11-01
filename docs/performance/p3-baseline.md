# P3 Performance Baseline

> Reproducible benchmark for the first stable release. Numbers are environment-specific; the
> meaningful signal is the *relative* overhead versus native FastAPI, not the absolute latency.

## Environment

| Attribute | Value |
|---|---|
| Date | 2026-11-01 |
| Hardware | Apple Silicon (aarch64), 18 vCPUs, 48 GB RAM (macOS host, Devcontainer) |
| Python | 3.12.16 |
| FastAPI | 0.162.0 |
| Starlette | 1.10.0 |
| Pydantic | 2.14.2 |
| uvicorn | 0.54.0 (single worker) |

## Methodology

- App under test: `examples/minimal-api` (`/api/hello`) versus a native FastAPI app with an
  identical `/api/hello` route.
- Server: single-process uvicorn on localhost, no OpenTelemetry instrumentation in the minimal app.
- Load driver: `scripts/benchmark.py`.
- Warm-up: 200 requests at concurrency 20 before measurement.
- Measurement: 2000 requests at concurrency 50.
- Latency is end-to-end client-perceived round-trip time; all four latency percentiles are
  reported because the tail (p99) is noisy in a containerized, bind-mounted environment.

## Results

| Target | p50 (ms) | p95 (ms) | p99 (ms) | mean (ms) | RSS after load |
|---|---|---|---|---|---|
| Apyra minimal-api | 41.09 | 169.83 | 252.05 | 58.46 | 73.8 MB |
| Native FastAPI | 37.79 | 160.55 | 266.62 | 55.39 | 75.7 MB |

## Interpretation

- Mean latency overhead of `apyra-fastapi` over native FastAPI is ~5.5% in this environment;
  the p50 delta is within single-digit percent and the p99 tail overlaps with noise.
- Memory footprint is comparable (Apyra ~74 MB vs native ~76 MB RSS after load).
- These are measurements, not a claim that Apyra is *faster* than FastAPI. Apyra adds settings
  normalization, structured logging, and lifecycle wiring on top of FastAPI; the measured cost of
  that layer is small and bounded.

## Reproduce

```bash
# Apyra
uv run --with uvicorn uvicorn main:app --app-dir examples/minimal-api --host 127.0.0.1 --port 8123 &
uv run python scripts/benchmark.py http://127.0.0.1:8123/api/hello --requests 2000 --concurrency 50

# Native FastAPI reference (identical route)
uv run --with uvicorn uvicorn native_app:app --app-dir /tmp --host 127.0.0.1 --port 8124 &
uv run python scripts/benchmark.py http://127.0.0.1:8124/api/hello --requests 2000 --concurrency 50
```
