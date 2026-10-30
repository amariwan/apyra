# Release Validation

## Isolated package installation

All 16 distributions were installed individually in fresh Python 3.12 virtual environments using only their built wheels and `--find-links dist`.

Result: all imports succeeded.

Validated packages:
- apyra-core
- apyra-fastapi
- apyra-db
- apyra-auth
- apyra-storage
- apyra-cache
- apyra-ai
- apyra-observability
- apyra-email
- apyra-channels
- apyra-i18n
- apyra-events
- apyra-security
- apyra-tasks
- apyra-cli
- apyra

## Metapackage

`apyra[all]` was installed in a fresh virtual environment.

Result: all optional package imports succeeded.

## Quality gates

- Ruff: passed
- Ruff format: passed
- MyPy: passed
- Pyright: passed
- Pytest: 69 tests passed
