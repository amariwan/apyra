# Installation

## Current verified path: source checkout

Package publication is not assumed. Until release artifacts are published and independently
verified, clone the repository and develop natively with Python 3.12+, `uv`, and `just` (no Docker
or Devcontainer required):

```bash
git clone https://github.com/amariwan/apyra.git
cd apyra
uv sync --all-packages --all-extras
```

All project Python commands can be run directly from the repository root. Docker and Devcontainers
are optional — see the sections below.

## Package selection after publication

The intended package model is:

```bash
uv add apyra-core apyra-fastapi
uv add 'apyra-db[postgres]'
uv add 'apyra-observability[opentelemetry]'
```

Do not copy these commands into an automated deployment until the named versions are present in the
configured package index. The `apyra` metapackage provides optional bundles, but individual packages
remain the clearest dependency contract.

## Verify the checkout

```bash
just check
```

Integration tests that report PostgreSQL or Redis as unavailable are skipped, not verified. Start
the configured services before treating those scenarios as passing. For PostgreSQL and Redis
integration tests, Docker Compose is optional — see [Optional: Docker Infrastructure](#optional-docker-infrastructure).

## Optional: Devcontainer

For a reproducible, isolated development environment, Apyra provides an optional Devcontainer
configuration in [`.devcontainer/`](../../.devcontainer/). Devcontainers are **not required**.

```bash
devcontainer up --workspace-folder .
devcontainer exec --workspace-folder . uv sync --all-packages --all-extras
devcontainer exec --workspace-folder . just check
```

## Optional: Docker Infrastructure

Docker and Docker Compose are optional tools for integration testing with PostgreSQL and Redis.
Core development does not require Docker. See [Testing Guide](../guides/testing.md).

Next: [Five-minute quickstart](quickstart.md).