# APYRA 0.1.0 — Publication Readiness

Preparation record for the first public release. **No packages have been
published.** This document is the authorization boundary: publication proceeds only
after explicit maintainer approval and a protected tag push.

Review update (2026-11-04): the current local worktree passed `just check` with isolated
PostgreSQL/Redis services (662 passed, none skipped), Mypy, Pyright, Ruff, strict documentation
checks, reproducible artifact-manifest verification, and isolated release validation. The
multi-process reliability and restart fault-injection harnesses have not run on this worktree:
the already-running Devcontainer lacks Docker CLI access; the new Docker-outside-of-Docker feature
requires a container rebuild. Hosted CI for the updated PR head is pending. No publication has
occurred.

---

## 1. Complete package matrix

All 20 distributions report version `0.1.0`. Five names were checked on PyPI
(`apyra`, `apyra-core`, `apyra-fastapi`, `apyra-db`, `apyra-auth` → HTTP 404,
i.e. unclaimed). Re-check all 20 names immediately before the first publish.

| Distribution | PyPI name | GitHub environment | Phase |
|---|---|---|---|
| apyra-core | apyra-core | pypi-core | core |
| apyra-ai | apyra-ai | pypi-ai | leaf |
| apyra-application | apyra-application | pypi-application | leaf |
| apyra-auth | apyra-auth | pypi-auth | leaf |
| apyra-cache | apyra-cache | pypi-cache | leaf |
| apyra-channels | apyra-channels | pypi-channels | leaf |
| apyra-cli | apyra-cli | pypi-cli | leaf |
| apyra-db | apyra-db | pypi-db | leaf |
| apyra-domain | apyra-domain | pypi-domain | leaf |
| apyra-email | apyra-email | pypi-email | leaf |
| apyra-events | apyra-events | pypi-events | leaf |
| apyra-i18n | apyra-i18n | pypi-i18n | leaf |
| apyra-messaging | apyra-messaging | pypi-messaging | leaf |
| apyra-observability | apyra-observability | pypi-observability | leaf |
| apyra-security | apyra-security | pypi-security | leaf |
| apyra-storage | apyra-storage | pypi-storage | leaf |
| apyra-tasks | apyra-tasks | pypi-tasks | leaf |
| apyra-workflow | apyra-workflow | pypi-workflow | leaf |
| apyra-fastapi | apyra-fastapi | pypi-fastapi | fastapi |
| apyra | apyra | pypi-meta | metapackage |

## 2. PyPI publisher readiness

- Trusted Publishing (`id-token: write`) is implemented per distribution behind the
  `pypi-*` environments listed above; actual provider/environment settings were not independently
  verified in this review.
- Environments should require review for production releases and restrict
  deployment to `main`/release tags (per `docs/release/runbook.md`).
- No long-lived PyPI API tokens are used.

## 3. Artifact hashes

Full SHA-256 digests for all 40 artifacts are in
`docs/audits/apyra-0.1.0-manifest.json` (machine-readable). Example:

| Artifact | SHA-256 |
|---|---|
| apyra_core-0.1.0-py3-none-any.whl | `7adf29212f1a5e53a277ab2560b3b0487a96cc2f60babea1c98a9e8435d41fc6` |
| apyra_core-0.1.0.tar.gz | `573b1dda7b2d6718c68cc1a9541795f6bfcab91a9a2c6109ddf013a3c1d47f34` |

(20 wheels + 20 sdists total; `scripts/check_pypi_artifacts.py` re-verifies local
vs published digests at publish time.)

## 4. GitHub workflow status

`publish.yml` is complete and dependency-aware:

1. `lock-check` → `quality` (3.12, 3.13) → `build` (attests provenance, uploads
   `release-distributions`) → `validate` (isolated install).
2. `publish-core` → `verify-core` (waits for PyPI, installs, imports).
3. `publish-leaf` (17-package matrix) → `verify-packages`.
4. `publish-fastapi` → `verify-fastapi`.
5. `publish-meta` → `smoke-test` (installs `apyra[all]` from PyPI, health check).
6. `github-release` (tag-triggered).

Manual `workflow_dispatch` defaults to `publish=false` (dry validation build);
`publish=true` is required to reach PyPI.

## 5. Publication order

1. `apyra-core` (publish + verify on PyPI).
2. 17 leaf packages in parallel (publish + verify each).
3. `apyra-fastapi` (after all leaf packages verified).
4. `apyra` metapackage (after fastapi + leaf verified).
5. External `apyra[all]` install smoke test.
6. GitHub Release (tag-triggered only).

## 6. Known experimental features

- Multi-worker workflow durability (single-process step execution today).
- Tenant isolation is repository-level only (no defense-in-depth for raw SQL).
- SQLAlchemy ≥2.1 OpenTelemetry instrumentation (upstream constraint).

## 7. Remaining technical limitations

- Monitoring middleware uses `BaseHTTPMiddleware` (correct timing semantics at
  streaming cost).
- Broader performance matrix beyond the JSON microbenchmark not recorded.
- Worker kill/restart and mid-run workflow-cancellation fault injection not exercised.
- No Apyra-managed Alembic environment or migration runner is implemented. A versioned SQL upgrade
  covers existing outbox/workflow schemas and the PostgreSQL idempotency table; PostgreSQL
  integration tests apply the scripts to pre-upgrade schemas.

## 8. Recovery procedure for partial publication

PyPI does not permit overwriting a published file with different content:

1. Inspect the failed job and PyPI state.
2. Fix without changing `0.1.0`.
3. Re-run failed and downstream jobs (`skip-existing: true` skips already-published
   files; `check_pypi_artifacts.py` rejects digest mismatches).
4. If `0.1.0` content must change, bump to `0.1.1` — never overwrite.

## 9. Release approval checklist

- [ ] All 20 distributions at a single version (`0.1.0`).
- [x] `uv run ruff check .`, `ruff format --check .`, `mypy`, `pyright` pass.
- [x] `just check` passes with Redis/PostgreSQL (662 passed, 0 skipped).
- [ ] Multi-process reliability passes with 8 processes (not run in the current Devcontainer).
- [x] PostgreSQL schema migration integration test passes for existing rows and all migration tables.
- [x] Two `uv build --all-packages` runs produce matching 40-artifact manifests; the checked-in
  manifest matches the current artifacts.
- [x] Isolated `scripts/validate_release.py` passes with the bundled manifest (`RELEASE VALIDATION OK`).
- [ ] Updated hosted CI passes, including the guarded restart harness.
- [ ] `pypi-*` protections and trusted publishers independently verified.
- [ ] Comprehensive secret scan completed (the local high-confidence pattern scan found no matches).
- [ ] Maintainer approval recorded.
- [ ] Push `v0.1.0` tag (or manual dispatch with `publish=true`).

**No commit, push, tag, or publication has been performed.**
