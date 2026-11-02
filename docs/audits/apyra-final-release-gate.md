# APYRA Final Release Gate

Point-in-time release-decision record. Every status is backed by an executed
check recorded below, not by the unit-test count alone. Statuses:
**PASS / FAIL / NOT VERIFIED / EXPERIMENTAL**.

---

## 1. Completed verification matrix

| Check | Command | Result |
|---|---|---|
| Lint | `uv run ruff check .` | PASS |
| Format | `uv run ruff format --check .` | PASS |
| Type check | `uv run mypy` + `uv run pyright` | PASS |
| Tests (Redis 8 + PostgreSQL 17) | `uv run pytest` | PASS (631 passed) |
| Package build | `uv build --all-packages` | PASS (20 wheels + 20 sdists) |
| Isolated install | `scripts/validate_release.py --dist dist` | PASS (`RELEASE VALIDATION OK`) |
| Security: Bandit | `uv run bandit -r packages -ll -q` | PASS (0 medium/high) |
| Security: pip-audit | `uv run pip-audit` | PASS (no known vulnerabilities) |
| Secret scan | grep for private keys/AWS keys/hardcoded creds | PASS (none found) |
| Multi-process reliability | `scripts/multi_process_reliability.py --processes 8` | PASS |
| Fault injection | `scripts/fault_injection.py` | PASS (Redis + PostgreSQL restart recovery) |

## 2. Multi-process test results — **PASS**

`scripts/multi_process_reliability.py` spawns real OS processes (not threads):

| Check (8 processes) | Result |
|---|---|
| Concurrent refresh-token rotation | exactly 1 winner |
| Concurrent idempotency claim | exactly 1 `CLAIMED` |

The Redis `_CONSUME_SCRIPT` Lua script and `SET NX` idempotency claim are atomic
across processes. This is atomic *consumption* (exactly-one-winner), **not** a
claim of end-to-end exactly-once delivery.

## 3. Fault-injection results — **PASS (partial)**

| Failure mode | Result |
|---|---|
| Redis restart during consumption | PASS — consumer logged `read failed; retrying`, recovered, processed a message after restart. |
| PostgreSQL restart | PASS — fresh session (`pool_pre_ping`) reconnected, `SELECT 1` succeeded. |
| Transaction rollback | PASS — existing outbox/db rollback tests. |
| Message redelivery / DLQ | PASS — existing messaging tests. |
| Worker kill/restart, connection interruption, workflow cancellation mid-run | NOT VERIFIED — not exercised as a live kill/restart harness. |

## 4. Security audit findings

- **pip-audit**: no known vulnerabilities in the third-party dependency graph. The
  20 `apyra-*` distributions are skipped (not yet on PyPI) — expected, not a finding.
- **Bandit** (`-ll`): 0 medium/high severity. 962 low-severity findings (assert
  statements, broad `except Exception` in retry/monitoring paths, `subprocess`
  without shell) are accepted noise for a test- and infrastructure-heavy codebase.
- **Secret scan**: no private keys, AWS access keys, or hardcoded credentials in
  `packages/*/src`.
- One confirmed defect (non-atomic concurrent refresh rotation) was fixed in P6
  with a Redis Lua script and is covered by both a thread-level and a
  process-level test.

## 5. Performance results

Reproducible in-process `httpx.ASGITransport` benchmark
(`scripts/benchmark_compare.py`), 5 routes:

| Configuration | req/s | p50 | p95 | p99 | CPU s | peak mem |
|---|---|---|---|---|---|---|
| FastAPI (bare) | 5670 | 5.77 ms | 9.88 ms | 19.16 ms | 0.55 | 5.04 MiB |
| Apyra (default) | 5387 | 6.31 ms | 10.91 ms | 18.13 ms | 0.58 | 5.21 MiB |
| Apyra (+monitoring) | 3411–3577 | 11.87 ms | 22.98 ms | 24.15 ms | 0.85 | 6.39 MiB |

Default overhead ~5%. Authenticated/PostgreSQL-CRUD/tenant/Redis/messaging/
workflow/multi-ASGI-worker benchmarks are **NOT VERIFIED** (only the JSON
microbenchmark exists). These are in-process microbenchmarks, not production
throughput claims.

## 6. Artifact integrity

- `uv build --all-packages` reproduces 40 artifacts (20 wheels + 20 sdists).
- SHA-256 digests computed for all artifacts (e.g. `apyra_ai-0.1.0`:
  `a3aad7a6…`); `scripts/check_pypi_artifacts.py` compares local vs published
  digests at publish time.

## 7. Package/version compatibility — **PASS**

- 20 distributions, all `0.1.0`, correct names, PEP 561 `py.typed` verified.
- Dependency extras verified (`[oidc]`, `[redis]`, `[outbox]`, `[s3]`,
  `[postgres]`, `[sqlite]`, `[mysql]`, `[migrations]`, `[openai]`, `[opentelemetry]`,
  `[celery]`, `[scheduler]`, `[taskiq]`, `[rabbitmq]`, `[memcached]`, `[websocket]`,
  `[providers]`, `[sdk]`, metapackage `[web]/[all]/…`).

## 8. PyPI publishing readiness — **PASS**

- Trusted Publishing configured (`id-token: write`) behind protected `pypi-*`
  environments per distribution (see `docs/release/runbook.md`).
- CI runs least privilege (`contents: read`, `pull-requests: read`).
- `skip-existing: true` + digest comparison prevent duplicate publication.

### Publication order (dependency-aware)

1. `apyra-core` (no internal deps)
2. Leaf packages in parallel: `apyra-application`, `apyra-domain`, `apyra-db`,
   `apyra-auth`, `apyra-storage`, `apyra-cache`, `apyra-ai`, `apyra-observability`,
   `apyra-email`, `apyra-channels`, `apyra-i18n`, `apyra-events`, `apyra-security`,
   `apyra-tasks`, `apyra-cli`
3. `apyra-messaging`, `apyra-workflow` (depend on `apyra-db`/`apyra-application`)
4. `apyra-fastapi` (depends on `apyra-auth`/`apyra-security`)
5. `apyra` metapackage (last; depends on everything)
6. External `apyra[all]` install smoke test.

## 9. Version strategy recommendation — **0.1.0 (pre-1.0)**

Recommend publishing **0.1.0**, explicitly marked pre-1.0. Do **not** bump to
`1.0.0` or `1.0.0rc1`, because:

- Multi-worker workflow durability is EXPERIMENTAL.
- Tenant isolation is repository-level only (no defense-in-depth for raw SQL).
- SQLAlchemy ≥2.1 OpenTelemetry instrumentation is unsupported upstream.
- The public API has shifted during hardening (e.g. `DatabaseSessionManager(host→url)`
  rename, new idempotency/revocation/tenant protocols) without a documented
  stability policy.

The "1.0" wording in prior mission titles is aspirational; the concrete,
consistent version across all manifests is 0.1.0. No version changes were made.

## 10. Remaining limitations (NOT VERIFIED / EXPERIMENTAL)

- Literal worker kill/restart and workflow-cancellation fault injection.
- Broader performance matrix (auth/DB/tenant/Redis/messaging/workflow/multi-worker).
- Multi-worker workflow durability (EXPERIMENTAL).
- Tenant isolation beyond the repository layer.
- SQLAlchemy 2.1 OTel instrumentation (third-party constraint).

## 11. Final GO / NO-GO — **GO (0.1.0, conditional)**

**GO** for publishing Apyra **0.1.0** as a pre-1.0 release, pending maintainer
approval and tag, provided the maintainer accepts the documented NOT VERIFIED items
above. No release-blocking defects remain: the one security-critical defect found
during certification (non-atomic concurrent refresh rotation) is fixed and
verified at both thread and process level.

**No publication, tagging, pushing, or merging was performed.**
