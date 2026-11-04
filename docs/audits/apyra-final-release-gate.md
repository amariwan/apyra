# APYRA Final Release Gate

Point-in-time release-decision record for the reviewed PR #7 patch on 2026-11-04.
Every status is backed by an executed check recorded below, not by the unit-test
count alone. Statuses:
**PASS / FAIL / NOT VERIFIED / EXPERIMENTAL**.

---

## 1. Completed verification matrix

| Check | Command | Result |
|---|---|---|
| Lint | `uv run ruff check .` | PASS |
| Format | `uv run ruff format --check .` | PASS |
| Type check | `uv run mypy`, `uv run pyright`, package `--verifytypes` | PASS (100% all public packages) |
| Tests | `just check` with isolated PostgreSQL 17 + Redis 8 | PASS (652 passed, 0 skipped) |
| Package build | `uv build --all-packages` | PASS (20 wheels + 20 sdists) |
| Isolated install | `uv run python scripts/validate_release.py --dist dist` | PASS (`RELEASE VALIDATION OK`) |
| Schema upgrade | `tests/integration/test_release_schema_migration.py` | PASS (existing rows retained; outbox/workflow/idempotency schemas created) |
| Security: Bandit | `uv run bandit -r packages -ll -q` | PASS (no medium/high findings) |
| Security: pip-audit | `just audit` | PASS (no known third-party vulnerabilities; Apyra packages not on PyPI yet) |
| Secret scan | local high-confidence key-pattern scan | No matches; comprehensive secret scanner NOT VERIFIED (`gitleaks` unavailable) |
| Multi-process reliability | `scripts/multi_process_reliability.py --processes 8` | PASS (one refresh winner and one idempotency claimant) |
| Fault injection | CI reliability step added; local invocation unavailable | NOT VERIFIED for current worktree; Devcontainer has no Docker CLI/socket |
| Workflow lint | `actionlint .github/workflows/ci.yml .github/workflows/publish.yml` | PASS |
| Documentation | `just docs-check` | PASS (strict build; pre-existing navigation/link notices remain) |

## 2. Multi-process test results — **PASS locally**

`scripts/multi_process_reliability.py` spawned eight real OS processes against a dedicated
disposable Redis service. Both checks passed against the current worktree.

| Check (8 processes) | Expected assertion |
|---|---|
| Concurrent refresh-token rotation | exactly 1 winner |
| Concurrent idempotency claim | exactly 1 `CLAIMED` |

The Redis `_CONSUME_SCRIPT` Lua script and `SET NX` idempotency claim are atomic
across processes. This is atomic *consumption* (exactly-one-winner), **not** a
claim of end-to-end exactly-once delivery.

## 3. Fault-injection results — **NOT VERIFIED for this worktree**

| Failure mode | Result |
|---|---|
| Redis restart during consumption | NOT VERIFIED locally — current CI test job now runs the guarded harness against a labeled disposable service. |
| PostgreSQL restart | NOT VERIFIED locally — current CI test job now runs the guarded harness against a labeled disposable service. |
| Transaction rollback | PASS in the PostgreSQL integration suite. |
| Message redelivery / DLQ | PASS in Redis integration tests, including malformed and exhausted messages. |
| Worker kill/restart, connection interruption, workflow cancellation mid-run | NOT VERIFIED. |

The current GitHub Actions run predates the latest local changes and failed type completeness in
the messaging/observability/workflow packages. Those issues now pass locally; no updated hosted run
has been observed because this worktree has not been pushed.

## 4. Security audit findings — current local scans

- **pip-audit**: no known vulnerabilities in the third-party dependency graph. The
  20 `apyra-*` distributions are skipped (not yet on PyPI) — expected, not a finding.
- **Bandit** (`-ll`): current local scan passed with no medium/high findings.
- **Secret scan**: high-confidence private-key/AWS/GitHub-token patterns had no matches in
  package source, scripts, or workflows. A comprehensive scanner was unavailable, so that gate
  remains unverified.
- Refresh-token consumption and family revocation now share one Redis Lua operation.
  Redis-backed regression tests passed in the current run against the isolated Redis service.

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
- SHA-256 digests were regenerated from the current 40 artifacts in
  `docs/audits/apyra-0.1.0-manifest.json`; `scripts/check_pypi_artifacts.py` compares local vs
  published digests at publish time.

## 7. Package/version compatibility — **PASS**

- 20 distributions, all `0.1.0`, correct names, PEP 561 `py.typed` verified.
- Dependency extras verified (`[oidc]`, `[redis]`, `[outbox]`, `[s3]`,
  `[postgres]`, `[sqlite]`, `[mysql]`, `[migrations]`, `[openai]`, `[opentelemetry]`,
  `[celery]`, `[scheduler]`, `[taskiq]`, `[rabbitmq]`, `[memcached]`, `[websocket]`,
  `[providers]`, `[sdk]`, metapackage `[web]/[all]/…`).

## 8. PyPI publishing readiness — **DOCUMENTED; EXTERNAL SETTINGS NOT VERIFIED**

- The workflow documents Trusted Publishing (`id-token: write`) behind per-package `pypi-*`
  environments and least-privilege permissions.
- Actual GitHub environment protections and PyPI trusted-publisher configuration were not
  inspected in this pass.
- `skip-existing: true` and digest comparison are implemented in the workflow.

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
- Apyra does not yet provide an Alembic environment or migration runner. The versioned SQL upgrade
  is documented and its PostgreSQL scripts are integration-tested; operators apply it through
  their chosen migration system.

## 11. Final GO / NO-GO — **NO-GO pending hosted checks and external release configuration**

The current worktree passes local quality, PostgreSQL/Redis integration, migration, build,
isolated-install, security, and multi-process checks. Release approval still requires a fresh hosted
CI run (including the newly added restart harness), verification of GitHub/PyPI protections, and a
comprehensive secret scan. These checks cannot be claimed from the earlier remote run or the local
regex scan.

**No publication, tagging, pushing, or merging was performed.**
