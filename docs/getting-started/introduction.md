# Introduction

Apyra is a Python 3.12+ workspace of independently publishable packages under the `apyra.*`
namespace. A small HTTP service needs only `apyra-core` and `apyra-fastapi`; database, authentication,
cache, messaging, task, workflow, and observability integrations stay optional.

## Design model

Applications compose explicit objects and framework adapters. Domain and application code can depend
on contracts without importing FastAPI, SQLAlchemy, Redis, or another infrastructure package. The
`apyra-core` package deliberately has no FastAPI or infrastructure dependency.

Apyra uses a PEP 420 implicit namespace. Import package APIs such as `apyra.core` or `apyra.db`; do
not create or depend on an `apyra/__init__.py` file.

## Supported baseline

- Python 3.12 and 3.13 are exercised by the repository CI configuration.
- The workspace uses `uv` for dependency resolution, builds, and execution.
- Async APIs are preferred at I/O boundaries.
- Public compatibility is package-scoped; optional backends require their declared extras.

Continue with [Why Apyra?](why-apyra.md), then use the [installation guide](installation.md).
