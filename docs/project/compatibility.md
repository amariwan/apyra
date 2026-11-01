# Compatibility and support policy

This document defines the supported versions, stability expectations, and deprecation
policy for Apyra packages.

## Supported Python versions

- Python 3.12 and 3.13 are supported and tested in CI.
- Python 3.11 and earlier are not supported.
- Python 3.14+ is not yet validated.

## Supported FastAPI versions

- `apyra-fastapi` requires `fastapi>=0.115.0`.
- The exact compatible FastAPI/Starlette combination is resolved by the package's
  dependency constraints and the lockfile used for development.

## Dependency compatibility

- Each `apyra-*` package declares its own dependency constraints in its `pyproject.toml`.
- Cross-package constraints follow `>=0.1.0,<0.2.0` during the 0.1.x series.
- Optional extras are only required when the corresponding feature is used.

## Public API stability

- The 0.1.x series is early-stage; APIs may change between minor releases.
- Public exports are those listed in each package's `__all__` and documented in the
  package README and API reference.
- Undocumented or private (underscore-prefixed) APIs are not part of the stable surface
  and may change without notice.

## Semantic versioning

- Versions follow Semantic Versioning (MAJOR.MINOR.PATCH).
- During 0.x, minor releases may include breaking changes; these are documented in the
  changelog and migration guides.
- After 1.0.0, breaking changes require a major version bump.

## Deprecation lifecycle

- Deprecated APIs are announced in the changelog with a replacement.
- Deprecated APIs remain functional for at least one minor release before removal.
- Removals are documented in migration guides.

## Migration policy

- Migration guides live under `docs/migrations/`.
- Each breaking change includes a migration note with before/after examples.

## Security update policy

- Security fixes are released as patch versions for the latest minor release.
- Only the latest released version of each package receives security fixes.
- See `SECURITY.md` for reporting vulnerabilities.

## Infrastructure requirements

- PostgreSQL and Redis integration tests require real services; see the test suite for
  markers and skip conditions.
- Delivery semantics: at-least-once delivery for messaging; idempotency is the
  application's responsibility. Exactly-once is not guaranteed.
