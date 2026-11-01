# Apyra — Final Release Readiness Report

**Date:** 2026-11-01
**Release candidate:** 0.1.0 (first stable public release)
**Recommendation:** **GO (conditional)** — publish after the two release-notes/CI follow-ups below are
completed and authorized. See "Remaining risks and follow-ups."

---

## 1. Release version and scope

- **Version:** `0.1.0` across all 20 distributions (consistent `[project].version`).
- **Scope:** 19 code distributions plus the `apyra` metapackage, published independently under
  PEP 420 implicit namespaces (`apyra.core`, `apyra.db`, …).
- **Supported Python:** 3.12 and 3.13 (tested in CI matrix); Python 3.11 and earlier unsupported.
- **License:** MIT. Root `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and
  `CHANGELOG.md` are present.

---

## 2. Quality-gate results

All gates were executed inside the Devcontainer (clean macOS host, no project packages installed
locally).

| Gate | Result |
|---|---|
| Ruff lint (`ruff check .`) | PASS — all checks passed |
| Ruff format (`ruff format --check .`) | PASS — 285 files formatted |
| mypy (strict) | PASS — no issues in 114 source files |
| Pyright | PASS — 0 errors, 0 warnings |
| Pytest (full suite) | PASS — **598 passed, 0 skipped** |
| Coverage | 94% (10,398 statements, 635 missed) |
| MkDocs build (`--strict`) | PASS — exit 0, no errors |
| Docs integration tests | PASS — 4 passed |

### Integration tests (previously skipped)

PostgreSQL 17 and Redis 8 were provisioned inside the Devcontainer, and the six previously-skipped
PostgreSQL/Redis integration tests now execute and pass:

- messaging outbox (PostgreSQL) — pass
- messaging Redis Streams — pass
- tasks scheduler reliability (PostgreSQL) — pass
- workflow persistence (PostgreSQL) — pass

CI now provisions the same services (see §7).

---

## 3. Security assessment

| Check | Result |
|---|---|
| `pip-audit` (third-party deps) | **No known vulnerabilities found** |
| `pip-audit` (local `apyra-*`) | Not auditable — packages are unpublished; documented blocker |
| Bandit (static, `-ll`) | **0 medium / 0 high** (879 low best-practice findings) |
| Hardcoded-secret grep (source) | None outside the distributed template's dev-only JWT fallback |

### Notable security posture (from the principal engineering audit)

- Bearer/refresh-token confusion, JWT expiry/revocation, ABAC null-condition, OAuth token-type
  normalization, and JWKS/OIDC endpoint trust issues were remediated and regression-tested.
- CSRF: the `cookie-auth` template enforces a ≥32-byte `APYRA_CSRF_SECRET`, binds CSRF tokens to the
  access-token cookie, and defaults cookies to `Secure` (HTTP only via explicit override).
- Secrets: credential-bearing settings use `repr=False`; structured JSON logging redacts
  Authorization/Cookie headers and compound credential keys.

### Security follow-ups (non-blocking)

- The distributed reference template still falls back to a development JWT secret; this is now
  documented in its generated README and `.env.example`. Recommend failing closed (require the env
  var) in a future iteration if the reference is promoted to production use.

---

## 4. Compatibility assessment

- 20 distributions enumerated; dependency direction (`core → domain → application → infrastructure
  → api`) verified; dependency graph is acyclic (integration test `test_dependency_graph_*`).
- `apyra-core` remains independent of FastAPI and infrastructure packages.
- `docs/project/compatibility.md` documents the 0.1.x semver policy, deprecation lifecycle, and
  Python/FastAPI support matrix.
- No undocumented breaking changes were introduced. The `apyra` metapackage `all` extra now includes
  the optional extras (`db[sqlite,postgres]`, `messaging[outbox,redis]`,
  `observability[opentelemetry]`, etc.) so the reference templates run from the `all` bundle.

---

## 5. Package verification

| Check | Result |
|---|---|
| Build | **20 wheels + 20 sdists** build cleanly (`uv build --all-packages`) |
| Isolated install | Each distribution installs into a fresh venv; public imports + `py.typed` verified |
| Release validation | `scripts/validate_release.py --dist …` → **RELEASE VALIDATION OK** |
| Generated projects | minimal, cookie-auth, modular-monolith, and distributed templates all validate |
| Quickstarts | minimal and cookie-auth quickstarts pass health/OpenAPI/JWT/CSRF checks |

---

## 6. Developer experience

- `apyra --help`, `apyra new` (with feature toggles), `apyra generate`, `apyra doctor`, and
  `apyra check` all execute successfully.
- A feature-enabled generated project imports and serves `/api/health` (HTTP 200).
- Template overwrite protection, safe-name validation, and `--dry-run` behavior are preserved.

---

## 7. CI/CD verification

### CI (`ci.yml`)

Change detection → lock-check → quality (3.12/3.13) → dependency-review (fail-on-high) →
actionlint → build → `attest-build-provenance` → install-smoke (isolated wheel + PEP 561) →
required-checks. Quality gate covers lint, typecheck (mypy + pyright + `--verifytypes`), strict docs
build, pytest with coverage, and security scans (pip-audit + Bandit).

### Publishing (`publish.yml`)

Version/metadata validation → build with provenance attestation → `validate_release.py` →
staged **PyPI Trusted Publishing** (`id-token: write` + `pypi-*` environments +
`attestations: true`) for core → leaf → fastapi → meta, with verify-after-publish → PyPI smoke test
(`apyra[all]` health) → GitHub release on tag.

### Provenance / SBOM

`actions/attest-build-provenance` produces SLSA provenance in both CI and publish; the PyPI publish
action publishes attestations (`attestations: true`).

### CI fix applied this cycle

The test job previously skipped the PostgreSQL/Redis integration tests (no services). It now
provisions `postgres:17` and `redis:8` service containers and sets `APYRA_TEST_POSTGRES_URL`,
`APYRA_TEST_POSTGRES_URL_SYNC`, and `APYRA_TEST_REDIS_URL`. A regression test
(`test_quality_test_job_provisions_postgres_and_redis_services`) locks this in.

---

## 8. Performance

Documented in `docs/performance/p3-baseline.md`. Apple Silicon (18 vCPU / 48 GB), Python 3.12.16,
FastAPI 0.162.0, uvicorn 0.54.0, 2000 requests at concurrency 50 after a 200-request warm-up:

| Target | p50 | p95 | p99 | mean | RSS |
|---|---|---|---|---|---|
| Apyra minimal-api | 41.09 ms | 169.83 ms | 252.05 ms | 58.46 ms | 73.8 MB |
| Native FastAPI | 37.79 ms | 160.55 ms | 266.62 ms | 55.39 ms | 75.7 MB |

Mean latency overhead ~5.5%; memory comparable. No claim of being faster than FastAPI is made.

---

## 9. Remaining risks and follow-ups

| # | Item | Severity | Status |
|---|---|---|---|
| 1 | **Hosted CI not yet run** for this worktree — requires pushing a branch (not authorized). | Medium | Pending push + review |
| 2 | **`pip-audit` cannot audit local `apyra-*` packages** (unpublished); only third-party deps audited. | Low | Resolves after first publish |
| 3 | **`CHANGELOG.md` 0.1.0 release notes** written this cycle. | — | Done |
| 4 | **SQLAlchemy 2.1.6 exceeds the opentelemetry-sqlalchemy instrumentor range (<2.1.0)** — SQLAlchemy instrumentation is skipped (warning only, app works). | Low | Pin or upgrade instrumentor |
| 5 | **MkDocs `--strict` leaves two "unrecognized relative link" INFOs** to the `.devcontainer/` directory. | Info | Cosmetic |
| 6 | **Material for MkDocs EOL May 2027** (successor: Zensical). | Info | Plan migration |
| 7 | **Distributed template dev JWT fallback** (documented, not fail-closed). | Low | Harden if promoted |
| 8 | PostgreSQL/Redis integration tests require services; verified locally and wired into CI, but not yet observed passing in hosted CI. | Low | Confirmed by CI run (item 1) |

No **critical** or **high** findings remain open.

---

## 10. GO / NO-GO recommendation

**GO (conditional).**

All locally-verifiable release gates pass: lint/type/format, full test suite (598 passed, 0 skipped)
including real PostgreSQL/Redis integration tests, security scans (no critical/high), strict docs
build, independent package build + isolated install + release validation, generated-project
validation, and a documented benchmark baseline.

Conditions to clear before publishing:

1. Push the branch and confirm hosted CI (quality matrix + publish `validate` job) is green
   (item 1). This is the only remaining external step.

No publication, tagging, or push has been performed. Explicit maintainer authorization is required
for all external publication steps.
