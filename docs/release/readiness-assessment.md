# Apyra 0.1.0 Release Readiness

Date: 2026-11-01

This page records the release gates that gate publication of Apyra 0.1.0. It is a point-in-time
assessment; the authoritative, reproducible commands live in the [release runbook](runbook.md) and the
[release validation](validation.md) notes.

## Gates

| Gate | Command | Status |
|---|---|---|
| Dependency synchronization | `uv sync --all-packages --all-extras` | PASS |
| Lockfile freshness | `uv lock --check` | PASS |
| Lint | `uv run ruff check .` | PASS |
| Formatting | `uv run ruff format --check .` | PASS |
| Type checking | `uv run mypy` and `uv run pyright` | PASS |
| Unit and integration tests | `uv run pytest` (Python 3.12 and 3.13) | PASS |
| Security audit | `uv run pip-audit` and `uv run bandit -r packages -ll -q` | PASS |
| Package build | `uv build --package ...` for all 20 distributions | PASS |
| Isolated install validation | `scripts/validate_release.py --dist dist` | PASS |
| Documentation | `mkdocs build --strict` | PASS |
| GitHub Actions | `ci.yml` quality, build, install-smoke, and required-checks jobs | PASS |

## Sign-off criteria

Publication proceeds only when every gate above is green on the release commit, package versions
across `packages/*/pyproject.toml` are identical, the metapackage core dependency range is current, and
the PyPI trusted-publishing environments described in the [runbook](runbook.md) are configured.

## Remaining items

- Release candidate tagging and publication (requires maintainer approval).

## Conclusion

Apyra 0.1.0 is engineering-complete. Publication is pending maintainer approval and tag.
