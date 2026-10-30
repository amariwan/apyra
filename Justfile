set shell := ["bash", "-euo", "pipefail", "-c"]
set dotenv-load := true
set export := true

# ----------------------------------------------------------------------
# Konfiguration
# ----------------------------------------------------------------------
UV := "uv"
PYTHON := "python"
HOST := env("HOST", "0.0.0.0")
PORT := env("PORT", "5000")

# ----------------------------------------------------------------------
# Default
# ----------------------------------------------------------------------
@default:
    just --list

# ----------------------------------------------------------------------
# Entwicklung
# ----------------------------------------------------------------------
sync:
    uv sync --all-packages --all-extras

dev:
    uv run uvicorn main:app --app-dir examples/minimal-api --host {{HOST}} --port {{PORT}} --reload


update:
    uv sync --upgrade --all-extras
# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------
test *args="":
    uv run pytest {{args}}

test-unit:
    uv run pytest -m unit

test-integration:
    uv run pytest -m integration

test-all:
    uv run pytest

test-cov:
    uv run pytest --cov=packages --cov-report=term-missing --cov-report=xml

# ----------------------------------------------------------------------
# Qualität
# ----------------------------------------------------------------------
lint:
    uv run ruff check .
    uv run ruff format --check .

fmt:
    uv run ruff format .

fix:
    uv run ruff check --fix .
    just fmt

mypy:
    uv run mypy

pyright:
    uv run pyright

check: lint mypy pyright test

# ----------------------------------------------------------------------
# Packaging
# ----------------------------------------------------------------------
build:
    for package in core fastapi storage db auth cache ai observability email channels i18n events security tasks cli; do \
      uv build --package "apyra-${package}"; \
    done
    uv build --package apyra

install-test:
    rm -rf /tmp/apyra-install-test
    python3.12 -m venv /tmp/apyra-install-test
    /tmp/apyra-install-test/bin/pip install dist/*.whl
    /tmp/apyra-install-test/bin/python -c "import apyra.core, apyra.fastapi, apyra.db, apyra.auth, apyra.storage, apyra.cache, apyra.ai, apyra.observability, apyra.email, apyra.channels; print('install ok')"

# ----------------------------------------------------------------------
# Aufräumen
# ----------------------------------------------------------------------
clean:
    rm -rf .venv .pytest_cache .ruff_cache .mypy_cache .pyright_cache \
           dist build htmlcov coverage.xml
    find . -type d -name "__pycache__" -exec rm -rf {} +
    find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete

audit:
    uv run pip-audit
