# APYRA 1.0 — Release Certification

> Historical certification for commit `721e9c9`. The 2026-11-04 PR review changed
> code covered by this record. Current local validation and remaining service-backed
> checks are recorded in `apyra-final-release-gate.md`; this earlier result set does
> not certify the reviewed patch.

Generated during the P6 release-certification pass. Statuses use an explicit
**PASS / FAIL / NOT VERIFIED / EXPERIMENTAL** vocabulary. Each section records the
evidence behind its status; nothing is claimed based solely on the unit-test count.

---

## 1. Architecture review — **PASS**

- 20 independently publishable distributions under the `apyra.*` PEP 420 namespace
  (no `apyra/__init__.py`; each concrete subpackage owns its own).
- Dependency direction is enforced: `apyra-core` has no FastAPI/infrastructure
  dependency; domain code does not import HTTP frameworks, databases, or brokers.
- Composition over inheritance; explicit dependency injection; no hidden global
  state in the application factory (`create_app` is pure and repeatable).
- Optional infrastructure is behind explicit extras (`[postgres]`, `[redis]`,
  `[oidc]`, `[outbox]`, `[s3]`, …); core stays lightweight.

## 2. Security findings — **PASS** (one defect fixed during certification)

| Area | Status | Evidence |
|---|---|---|
| Password hashing | PASS | PBKDF2-SHA256, 600k iterations, per-hash salt, iteration bounds, rehash detection. |
| API keys | PASS | SHA-256 digest + `hmac.compare_digest`. |
| CSRF | PASS | HMAC-SHA256 signed token, optional binding, constant-time compare, 32-byte secret minimum. |
| Secrets/redaction | PASS | Nested redaction of `password`/`token`/`secret`/`authorization`/`cookie`/`api_key` keys. |
| JWT validation | PASS | Mandatory signature + `exp`; issuer/audience enforced when configured; `sub`/`iat`/`exp` required. |
| Refresh-token rotation | PASS | Atomic consume; reuse revokes the whole family. |
| Concurrent refresh rotation | PASS | **Fixed during certification**: `RedisRevocationStore.consume_refresh_token_until` was check-then-revoke (non-atomic). Replaced with a Redis Lua script (`_CONSUME_SCRIPT`) so exactly one of N concurrent rotations wins. Verified by `test_concurrent_refresh_rotation_yields_single_success` (8 threads → 1 success). |
| Tenant isolation | PASS (scoped) | `TenantScopedRepository` fail-closes reads/count/paginate/`get`. See §3 for the stated boundary. |

## 3. Reliability guarantees

- **Messaging (Redis Streams)** — **at-least-once** delivery. Abandoned pending
  messages are recovered (`XPENDING`/`XCLAIM`) and re-processed; exponential
  backoff; dead-letter after `max_attempts`; duplicate suppression via idempotency
  stores. Exactly-once is **not** claimed.
- **Transactional outbox** — **at-least-once** publish. Atomic claim
  (`FOR UPDATE SKIP LOCKED`), `leased_by`/`fencing_token` ownership, `version_id`
  optimistic concurrency (stale workers raise `StaleDataError`), dead-letter after
  `max_attempts`.
- **Idempotency** — atomic `claim`/`complete` (Redis `SET NX`, PostgreSQL
  `INSERT … ON CONFLICT DO NOTHING` + expired takeover). Duplicate detection + crash
  recovery (TTL-based). In-memory store remains for development/tests.
- **Workflow** — steps commit per-step (no repeated completed step after crash);
  `reconstruct`/`resume`; per-step timeouts; cancellation is resumable.
  **Multi-worker workflow durability is EXPERIMENTAL** (the engine runs steps
  in-process; `claim_pending`/`recover_expired` exist but are not wired into a
  multi-process dispatcher).

### Tenant isolation boundary (explicit)

Tenant isolation is guaranteed **at the repository layer** via
`TenantScopedRepository`/`TenantScopedMixin`. It does **not** claim defense-in-depth
against raw SQL, ad-hoc queries, or a non-scoped `Repository` used against a
tenant-model — applications must use the scoped repository for tenant-protected
data. This is documented, not silently assumed.

## 4. Multi-worker test results — **HISTORICAL**

Verified against real Redis 8 and PostgreSQL 17:

| Scenario | Result |
|---|---|
| Concurrent refresh rotation (8 threads) | exactly 1 winner |
| Concurrent Redis idempotency claim (3 tasks) | exactly 1 `CLAIMED`, 2 `IN_PROGRESS` |
| Concurrent outbox claim (`skip_locked`) | no overlapping claim |
| Stale outbox worker write (`version_id`) | `StaleDataError` |
| Expired outbox/workflow lease recovery | recovered |
| Abandoned Redis Streams message recovery | re-processed |
| Dead-letter after retry exhaustion | moved to DLQ, source removed |

A multi-OS-process stress harness was added in this PR, but it was not executed
during the 2026-11-04 review because the Apyra Redis/PostgreSQL test services were
unavailable. Multi-process orchestration is **NOT VERIFIED** for the reviewed patch.

## 5. Benchmark methodology and results

In-process `httpx.ASGITransport` benchmark (removes network/server-process overhead;
measures framework/middleware cost). 5 routes, `--requests`/`--concurrency`
configurable; several runs compared (medians). See `scripts/benchmark_compare.py`.

| Configuration | req/s | p50 | p95 | p99 | CPU s | peak mem |
|---|---|---|---|---|---|---|
| FastAPI (bare) | 5670 | 5.77 ms | 9.88 ms | 19.16 ms | 0.55 | 5.04 MiB |
| Apyra (default) | 5387 | 6.31 ms | 10.91 ms | 18.13 ms | 0.58 | 5.21 MiB |
| Apyra (+monitoring) | 3411–3577 | 11.87 ms | 22.98 ms | 24.15 ms | 0.85 | 6.39 MiB |

Default Apyra overhead is ~5% (was ~26% before `SecurityHeadersMiddleware` was
converted from `BaseHTTPMiddleware` to pure ASGI). Monitoring is opt-in and its
cost is the timing/recording work plus `BaseHTTPMiddleware` streaming. These are
in-process microbenchmarks and are **not** a production throughput claim.

## 6. External consumer validation — **PASS**

`scripts/validate_release.py` installs all 20 distributions into isolated venvs
(wheel + sdist), verifies `py.typed` markers, installs `apyra[all]`, then generates
and validates the quickstarts and templates end-to-end. Output: **RELEASE
VALIDATION OK**.

## 7. Package matrix — **PASS**

- 20 distributions, all `0.1.0`, correct names (`apyra-core`, …, `apyra`
  metapackage).
- `uv build --all-packages` produces 20 wheels + 20 sdists (40 artifacts).
- PEP 561 `py.typed` markers verified during isolated-install validation.

## 8. Dependency and supply-chain status — **PASS**

- CI runs with least privilege (`permissions: contents: read, pull-requests: read`).
- PyPI publish uses Trusted Publishing (`id-token: write`) behind protected
  `pypi-*` environments with a package matrix.
- Dependency security tooling configured: `pip-audit`, `bandit` (dev group).
- `uv lock --check` in CI enforces lockfile freshness.

## 9. Unsupported / experimental capabilities — **EXPERIMENTAL**

- Multi-worker workflow durability (single-process step execution today).
- SQLAlchemy ≥2.1 OpenTelemetry instrumentation (upstream instrumentor supports
  `<2.1.0`; `instrument_sqlalchemy` now reports this honestly and returns `False`).
- Monitoring middleware uses `BaseHTTPMiddleware` (correct full-response timing
  semantics at the cost of streaming overhead).

## 10. Known limitations

- Tenant isolation is repository-level only (see §3 boundary).
- Refresh-token family revocation on reuse is now part of the same Redis Lua
  operation as token consumption; the reviewed change still requires a Redis-backed
  test run.
- The multi-process and Redis/PostgreSQL restart harnesses exist but were not run
  during review because their services were unavailable.

## 11. Release blockers

Release readiness is **NOT VERIFIED** for the reviewed patch. The following remain
open rather than passed:

- Redis/PostgreSQL integration tests, including multi-process stress (§4).
- Controlled Redis/PostgreSQL restart fault injection (P6.6).
- A reviewed migration path for existing outbox/workflow schemas; no migration
  runner is implemented yet.

## 12. Readiness assessment — **NOT VERIFIED for the reviewed patch**

The reviewed patch passed local Ruff, formatting, Mypy, Pyright, package build, and
isolated release validation. Its full local test run passed 613 tests and skipped 28
Redis/PostgreSQL tests because those services were unavailable. The release is
**not** published. Re-run the service-backed checks before approval.
