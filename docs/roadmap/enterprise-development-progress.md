# Enterprise Development Progress

Updated: 2026-11-04

## Current phase

P3–P7 release hardening review. **Status: PARTIAL** — local quality, service-backed,
artifact, migration, security, and multi-process checks pass. Release approval awaits a fresh hosted
CI run (including restart fault injection), external GitHub/PyPI settings verification, and a
comprehensive secret scan.

## Completed in this iteration

- Tenant-scoped repository reads now cover composite keys; create, update, and delete
  enforce the configured tenant.
- Redis refresh reuse revokes the token family atomically through the latest linked
  token expiry. Idempotency claims use owner checks and can be safely released after
  handler failure.
- Redis Streams retry recovery waits for abandonment before dead-lettering, keeps
  source entries available to other consumer groups, and the fault harness verifies
  the specific post-restart message.
- Workflow resume validates persisted state and step sequence, retries failed steps,
  and commits retry progress.
- Preserved the deprecated database `host` keyword as a warning-emitting alias and
  corrected tenant integration and release-evidence docs.
- Rebuilt all 40 distribution artifacts and regenerated the publication manifest.
- Audited Python logging usage: package source has no ad hoc diagnostic `print()` calls;
  retained prints are intentional CLI/user, generator status, machine-readable stdout,
  benchmark/report, automation, and README illustrative output. The periodic-task
  module now uses the established `logging.getLogger(__name__)` pattern. Fault-injection
  exception details use the configured Apyra logger while PASS/FAIL summaries remain on
  stdout. Added focused regression tests for both logging paths.
- Added mandatory Apyra engineering standards for functions, public/HTTP APIs, package boundaries,
  async and persistence behavior, security, logging, tests, and documentation. Linked them from
  `AGENTS.md` and the docs navigation; aligned contributor/testing guides with the required
  Devcontainer workflow.
- Revalidated tenant ownership against persisted rows under a lock before update/delete; added
  stale-owner regression coverage.
- Routed malformed Redis Stream payloads through configured dead-letter sinks, redacted exception
  details from messaging logs, and retained exhausted entries as pending when no sink is configured.
- Made pending-message recovery scan one bounded page per pass with a persistent cursor so a growing
  pending list cannot block normal stream reads or starve later abandoned entries.
- Added additive SQL migrations for existing outbox/workflow schemas and the PostgreSQL idempotency
  table, with a PostgreSQL integration test that preserves existing rows.
- Guarded fault injection against non-local or unlabeled Redis/PostgreSQL targets and added the
  multi-process/restart harness to the Python 3.12 CI service job.
- Fixed public type-completeness diagnostics for SQLAlchemy metadata and logger exports.

## Validation evidence

- `just check` with isolated Redis 8/PostgreSQL 17 services: Ruff, format, Mypy, Pyright passed;
  652 tests passed, 0 skipped.
- Logging audit verification: `git diff --check` passed; focused package/import checks passed;
- Service-backed Redis/PostgreSQL integration tests and the PostgreSQL schema migration test passed.
- `scripts/multi_process_reliability.py --processes 8`: PASS, one refresh winner and one idempotency
  claimant.
- `uv build --all-packages`: 20 wheels and 20 source distributions built; the artifact manifest was
  regenerated from the current build.
- `scripts/validate_release.py --dist dist`: `RELEASE VALIDATION OK`.
- `just docs-check`: documentation tests and strict MkDocs build passed.
- `just audit` and Bandit passed; pip-audit found no known vulnerabilities in
  third-party dependencies (Apyra's unpublished distributions are not auditable on PyPI).
- A local high-confidence secret-pattern scan found no matches; a comprehensive scanner is
  unavailable.
- GitHub Actions on the previous worktree failed package type completeness; all packages now pass
  local `pyright --verifytypes` at 100%. No updated hosted run has been observed.
- Guarded restart fault injection is in CI but could not run locally because the Devcontainer has
  no Docker CLI/socket.

## Remaining blockers and next goal

1. Run updated hosted CI, including the guarded restart fault-injection harness.
2. Verify actual GitHub protected environments and PyPI trusted-publisher configuration.
3. Run a comprehensive secret scanner and record its result.
4. Refresh the final release decision from current evidence.

Next goal: complete G9 verified-release evidence after hosted and external checks pass.
