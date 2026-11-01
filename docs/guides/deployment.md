# Deployment

Apyra applications are ASGI applications. Package and run them like a FastAPI service, with explicit
startup/shutdown ownership for databases, cache clients, brokers, schedulers, and telemetry.

## Minimum production checklist

1. Build and install pinned artifacts in a clean image; do not run from a writable source checkout.
2. Apply reviewed database migrations before incompatible application code starts.
3. Configure trusted proxy handling, HTTPS, host/origin policy, CORS, and shared rate limiting.
4. Use an external identity provider or managed keys; never ship development HMAC secrets.
5. Expose liveness separately from readiness checks for required infrastructure.

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 5000 --workers 2
```

Multiple workers do not share in-memory rate limits, caches, schedulers, or idempotency state. Use
shared infrastructure or elect a single scheduler owner when the behavior must be process-wide.

On shutdown, stop accepting work, drain in-flight tasks within a deadline, close clients, and flush
telemetry. Validate this sequence in the target container/orchestrator. See the
[release runbook](../release/runbook.md) for artifact controls.
