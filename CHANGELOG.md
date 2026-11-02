# Changelog

## Unreleased

- Add `RedisRevocationStore` (`apyra-auth`) for distributed, multi-instance token revocation with
  refresh-token reuse detection, plus a `redis` extra.
- Add multi-tenancy foundation: `TenantScopedMixin` and `TenantScopedRepository` (`apyra-db`) that
  fail-closed on cross-tenant reads, and a request-scoped tenant context (`apyra-security`).
- Add per-step timeouts to the workflow engine (`step_timeout_seconds`) with retry-then-fail and
  resumable cancellation semantics.
- Convert the default `SecurityHeadersMiddleware` (`apyra-fastapi`) from `BaseHTTPMiddleware` to a
  lightweight pure-ASGI middleware, reducing default request overhead from ~26% to ~5% while
  preserving identical header behavior.
- Make `instrument_sqlalchemy` report the SQLAlchemy ≥2.1 instrumentation gap honestly (returns
  `False` and warns) instead of claiming success.
- Extend `scripts/benchmark_compare.py` with CPU and peak-memory measurement.

- Rewrite the Redis Streams consumer (`apyra-messaging`) to recover abandoned pending messages
  (via `XPENDING`/`XCLAIM`) and process them through the same path as new messages, with
  exponential backoff, configurable retry limits, and dead-lettering. Delivery is at-least-once.
- Harden the transactional outbox with worker ownership (`leased_by`), fencing tokens, and
  optimistic concurrency (`version_id`) so a stale worker cannot overwrite state owned by another
  worker, plus poll/lease indexes and state-transition validation.
- Add distributed idempotency stores (`RedisIdempotencyStore`, `PostgresIdempotencyStore`) with
  atomic claim/complete semantics, TTL expiration, duplicate detection, and crash recovery.
- Persist per-step workflow state, add `WorkflowRepository.reconstruct`/`WorkflowEngine.resume`,
  and add worker ownership and optimistic concurrency to `apyra-workflow`; multi-worker workflow
  durability remains experimental.
- Rename `DatabaseSessionManager`'s constructor parameter `host` to `url` (it accepts a full
  database URL) and document it.

- Add error and performance monitoring primitives to `apyra-observability`, including bounded in-memory reporters, capture helpers, context managers/decorators, aggregated timing statistics, and manual timers.
- Add FastAPI error and performance monitoring middleware, registration helpers, and opt-in `create_app` flags (`error_monitoring`, `performance_monitoring`).

- Require configured expected issuer and audience values when JWT claim verification is enabled.
- Include configured issuer and audience claims in tokens issued by `TokenService` and enforce them
  during refresh, revocation, and access-token verification.
- Missing OAuth token response `token_type` temporarily defaults to `Bearer` with a
  `DeprecationWarning`; providers must return `token_type` before the next major `apyra-auth` release.
- Incomplete custom `EventBus` subclasses remain temporarily instantiable with a
  `DeprecationWarning`; implement both `publish()` and `subscribe()` before the next major
  `apyra-events` release.
- Repair release workflow dependency graph, version propagation, tag glob, manual dispatch guard, recovery-friendly publishing, and add automated workflow validation tests.
- `apyra new <name> --template cookie-auth` generates an opt-in cookie-auth integration starter
  with CSRF protection on unsafe routes; the default minimal starter is unchanged.

## 0.1.0

Initial release of the Apyra framework workspace.

### Packages

- `apyra-core`
- `apyra-application`
- `apyra-domain`
- `apyra-fastapi`
- `apyra-db`
- `apyra-auth`
- `apyra-storage`
- `apyra-cache`
- `apyra-ai`
- `apyra-observability`
- `apyra-email`
- `apyra-channels`
- `apyra-i18n`
- `apyra-events`
- `apyra-messaging`
- `apyra-workflow`
- `apyra-security`
- `apyra-tasks`
- `apyra-cli`
- `apyra` (metapackage)

### Quality

- Ruff, Ruff format, MyPy, Pyright, and Pytest pass.
- All distributions build and install in isolated environments.
