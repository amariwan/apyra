# Release validation

## Isolated package installation

All 20 distributions are installed individually in fresh Python 3.12 virtual environments from their
built wheels, with local Apyra dependencies resolved through `--find-links`.

Each wheel import and PEP 561 marker is checked. The corresponding sdist is then force-reinstalled
without dependencies and checked again.

Validated packages:
- apyra-application
- apyra-core
- apyra-domain
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
- apyra-messaging
- apyra-security
- apyra-tasks
- apyra-workflow
- apyra-cli
- apyra

## Metapackage

`apyra[all]` is installed in another fresh virtual environment with every local Apyra wheel path
passed explicitly to pip; third-party dependencies may resolve from the configured package index.

Result: all 19 importable package modules and their `py.typed` markers are validated.

## Independent generated consumers

The same isolated metapackage environment invokes its installed `apyra` console script for the
minimal, cookie-auth, modular-monolith, and distributed golden-path templates:

- `minimal-api`: verifies `/api/health` returns `{"status":"ok"}` and `/docs` returns HTTP 200.
- `cookie-auth-api`: verifies an unauthenticated request returns 401, validates a real signed HS256
  access token with issuer/audience/type/expiry claims, obtains a bound CSRF token, rejects a missing
  CSRF header, and accepts the protected `POST /write`.
- `modular-monolith-api`: verifies `/api/health` returns `{"status":"ok"}`.
- `distributed-api`: verifies `/api/health` returns `{"status":"ok"}` and exercises the generated
  order creation/read workflow.

The HMAC configuration is local to the disposable test. Production authentication should use a
trusted asymmetric issuer/JWKS configuration.

## Command

Build into a fresh temporary directory and pass that exact directory to the validator. See the
[quickstart maintainer proof](../getting-started/quickstart.md#maintainer-proof-clean-built-artifacts)
for the complete Devcontainer command.

Expected terminal markers:

```text
QUICKSTART VALIDATION OK
RELEASE VALIDATION OK
```

## Quality gates

Artifact validation is one release gate. It does not replace Ruff, formatting, mypy, Pyright, the
complete pytest suite, security scans, infrastructure integration tests, or documentation validation.
Use the [release runbook](runbook.md) and record current counts rather than retaining stale totals in
this page.
