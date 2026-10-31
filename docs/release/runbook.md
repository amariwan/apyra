# Apyra Release Runbook

## Prerequisites

- Python 3.12 and 3.13 quality gates pass.
- `uv sync --all-packages --all-extras` succeeds.
- All package versions in `packages/*/pyproject.toml` are identical.
- `CHANGELOG.md` is updated.
- GitHub environments and PyPI trusted publishers are configured.

## GitHub environments and trusted publishers

Create one protected GitHub environment per distribution:

| PyPI project | GitHub environment | Workflow file |
|---|---|---|
| apyra-core | pypi-core | publish.yml |
| apyra-ai | pypi-ai | publish.yml |
| apyra-auth | pypi-auth | publish.yml |
| apyra-cache | pypi-cache | publish.yml |
| apyra-channels | pypi-channels | publish.yml |
| apyra-cli | pypi-cli | publish.yml |
| apyra-db | pypi-db | publish.yml |
| apyra-email | pypi-email | publish.yml |
| apyra-events | pypi-events | publish.yml |
| apyra-fastapi | pypi-fastapi | publish.yml |
| apyra-i18n | pypi-i18n | publish.yml |
| apyra-observability | pypi-observability | publish.yml |
| apyra-security | pypi-security | publish.yml |
| apyra-storage | pypi-storage | publish.yml |
| apyra-tasks | pypi-tasks | publish.yml |
| apyra | pypi-meta | publish.yml |

Each PyPI project must use trusted publishing with:

- Owner: `amariwan`
- Repository: `apyra`
- Workflow: `publish.yml`
- Environment: the matching value above

Recommended environment protections:

- Required reviewers for production releases.
- Deployment branches restricted to `main` and release tags.
- No long-lived PyPI API tokens in GitHub secrets.

## Release preparation

1. Ensure `main` is clean and up to date.
2. Update all package versions consistently.
3. Run local quality gates:

   ```bash
   uv run ruff check .
   uv run ruff format --check .
   uv run mypy
   uv run pyright
   uv run pytest
   ```

4. Build and validate distributions:

   ```bash
   just build
   uv run --no-project --python 3.12 scripts/validate_release.py --dist dist
   ```

5. Run workflow validation:

   ```bash
   actionlint .github/workflows/ci.yml .github/workflows/publish.yml
   ```

## Release execution

Releases are triggered by pushing a validated tag:

```bash
git tag v0.1.0
git push origin v0.1.0
```

Manual dispatch is available for validation builds. Publishing requires `publish=true`.

## Release order

1. `apyra-core`
2. Leaf packages in parallel
3. `apyra-fastapi`
4. `apyra` metapackage
5. External installation smoke test

Each dependent package waits for successful publication and PyPI availability of its internal dependencies.

## Verification

- GitHub Actions quality, build, validation, publish, verify, and smoke-test jobs succeed.
- PyPI shows all 16 distributions at the release version.
- `apyra[all]` installs from PyPI in an isolated environment.
- FastAPI smoke test passes.

## Partial-release recovery

PyPI does not allow overwriting an existing distribution with different content.

If a later job fails:

1. Inspect the failed job and PyPI state.
2. Fix the underlying issue without changing the release version.
3. Re-run the failed and downstream jobs.
4. `skip-existing: true` prevents duplicate publication.
5. `scripts/check_pypi_artifacts.py` compares local and published SHA-256 digests before publishing.

If the same version requires different content, create a new patch version instead of overwriting.

## External installation

Consumers can install:

```bash
uv add apyra-fastapi
uv add "apyra[all]"
```

or:

```bash
pip install apyra-fastapi
```

Installations must resolve only from PyPI, never from local workspace paths.
