# API Migration and Cookie-Auth Starter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Stage two safe public API compatibility changes with deprecation warnings and add an opt-in cookie-auth integration starter protected by CSRF.

**Architecture:** Keep migration behavior at the affected API boundaries: OAuth response normalization in `OAuth2Client` and subclass compatibility in `EventBus`. Add the cookie-auth option to the existing CLI generator, using Apyra's existing auth and CSRF APIs without adding login, persistence, or provider abstractions.

**Tech Stack:** Python 3.12+, argparse, pytest, FastAPI, Apyra auth/security packages.

**Spec:** `docs/superpowers/specs/2026-10-31-api-migration-and-cookie-auth-starter.md`

## Global Constraints

- Keep `apyra-core` independent from FastAPI and infrastructure packages.
- Preserve the minimal starter as the default and preserve generated-file overwrite protection.
- Retain strict security validation; do not add insecure OIDC/JWT/revocation/cache fallbacks.
- Do not select a release number, publish packages, or merge PRs.
- Preserve unrelated pre-existing worktree changes.

## Review Focus

- Missing, empty, and wrong-typed OAuth `token_type` values must distinguish the deprecated missing-field case from invalid values.
- Complete built-in `EventBus` implementations must not emit warnings during import or construction.
- CSRF cookie/header mismatches and tokens bound to a different access-token cookie must fail closed.
- Missing or short CSRF secrets must stop the cookie-auth starter clearly before serving requests.
- Generated cookie settings must default to `Secure` and allow HTTP only through an explicit local-development override.

---

### Task 1: Deprecate missing OAuth token type

**Files:**
- Modify: `packages/auth/src/apyra/auth/oauth2.py`
- Test: `packages/auth/tests/test_oauth2.py`
- Test: `packages/auth/tests/test_oidc_client.py`
- Modify: `packages/auth/README.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: `OAuth2Client._token_request(data: dict[str, str]) -> OAuth2TokenResponse`.
- Produces: Missing `token_type` normalizes to `"Bearer"` and emits a caller-facing `DeprecationWarning` stating removal is no earlier than the next major `apyra-auth` release; invalid present values continue to raise `ValueError`.

- [x] **Step 1: Add regression tests** for a missing token type returning `Bearer` with exactly one `DeprecationWarning` containing `token_type` and `next major`, a present valid token type emitting no warning, and empty/non-string values still raising `ValueError`.
- [x] **Step 2: Run** `uv run pytest packages/auth/tests/test_oauth2.py -q`; confirm the missing-token-type test fails before the implementation.
- [x] **Step 3: Implement** the fallback with `warnings.warn(..., DeprecationWarning, stacklevel=2, skip_file_prefixes=(str(Path(__file__).parent),))` at the response parsing boundary so internal auth wrappers are skipped and the warning points to the consumer call site; leave invalid present values rejected.
- [x] **Step 4: Run** `uv run pytest packages/auth/tests/test_oauth2.py -q` and `uv run ruff check packages/auth/src/apyra/auth/oauth2.py packages/auth/tests/test_oauth2.py`.
- [x] **Step 5: Document** the provider migration and next-major removal milestone in the auth README and changelog.

### Task 2: Deprecate incomplete EventBus subclasses

**Files:**
- Modify: `packages/events/src/apyra/events/bus.py`
- Test: `packages/events/tests/test_events.py`
- Modify: `packages/events/README.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: `EventBus.publish(event: Event) -> list[BaseException]` and `EventBus.subscribe(event_name: str, handler: Handler) -> None`.
- Produces: Base methods temporarily raise `NotImplementedError`; defining each incomplete downstream subclass emits one caller-facing `DeprecationWarning` stating abstract enforcement is no earlier than the next major `apyra-events` release; complete adapters remain warning-free.

- [x] **Step 1: Add tests** for incomplete subclass definition warning (including exactly one warning and the next-major milestone), runtime failure when its unimplemented method is called, and no warning for `InMemoryEventBus`, `RabbitMQEventBus`, and `RedisStreamEventBus`.
- [x] **Step 2: Run** `uv run pytest packages/events/tests/test_events.py -q`; confirm the warning compatibility test fails against the abstract base.
- [x] **Step 3: Implement** concrete `EventBus` methods that raise `NotImplementedError` and `__init_subclass__` completeness detection that warns once for every subclass lacking either required override, using `stacklevel=2`. Complete built-in adapters must not warn at import or subclass creation.
- [x] **Step 4: Run** `uv run pytest packages/events/tests/test_events.py -q` and `uv run ruff check packages/events/src/apyra/events/bus.py packages/events/tests/test_events.py`.
- [x] **Step 5: Document** the required overrides and next-major abstract-enforcement milestone in the Events README and changelog.

### Task 3: Add an opt-in cookie-auth CLI starter

**Files:**
- Modify: `packages/cli/src/apyra/cli/main.py`
- Test: `packages/cli/tests/test_cli.py`
- Modify: `packages/cli/README.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: CLI command `apyra new <name> [--force]` and public `apyra.fastapi.require_csrf`, `apyra.security.generate_csrf_token`, `apyra.fastapi.get_current_token`.
- Produces: `apyra new <name> --template minimal|cookie-auth`; default is `minimal`. Cookie-auth output has authenticated `GET /csrf` and authenticated, CSRF-protected `POST /write`, reads `APYRA_CSRF_SECRET`, and documents external auth-provider responsibilities.

- [x] **Step 1: Add CLI tests** that assert default minimal output remains unchanged, cookie-auth output includes auth and CSRF dependencies, generated README states required provider settings, and existing overwrite behavior still applies.
- [x] **Step 2: Add generated-app tests** by importing generated `main.py` from a temporary project and overriding `get_current_token` in `app.dependency_overrides`. Assert `GET /csrf` requires the access cookie, emits a script-readable `csrf_token` cookie with `SameSite=Lax`, default `Secure`, and honors only `APYRA_COOKIE_SECURE=false`; assert `POST /write` accepts a token bound to the access cookie and rejects missing, mismatched, and wrong-binding tokens. Assert absent/short `APYRA_CSRF_SECRET` fails in a subprocess import.
- [x] **Step 3: Run** `uv run pytest packages/cli/tests/test_cli.py -q`; confirm the new CLI option and generated behavior fail before implementation.
- [x] **Step 4: Implement** template selection and generated source using the existing security APIs. Require a 32-byte-minimum `APYRA_CSRF_SECRET` during app import, bind CSRF tokens to the incoming access-token cookie, and accept only `APYRA_COOKIE_SECURE=true|false` (default `true`). Set the CSRF cookie with `httponly=False`, `samesite="lax"`, and the resolved `secure` value.
- [x] **Step 5: Run** focused CLI tests and `uv run ruff check packages/cli/src/apyra/cli/main.py packages/cli/tests/test_cli.py`.
- [x] **Step 6: Document** the cookie starter's prerequisites, TLS/Origin responsibilities, and example provider integration boundary; update the changelog.

### Task 4: Update audit migration status

**Files:**
- Modify: `docs/audits/2026-10-30-principal-engineering-audit.md`

- [x] **Step 1: Update** the compatibility disposition, draft consumer migration notes, and CSRF decision to reflect the approved staged migration and cookie-auth starter scope.
- [x] **Step 2: Verify** the audit distinguishes implemented behavior, deferred major-version removals, immediate security-driven changes, and hosted versus local validation evidence.

### Task 5: Cross-package verification and review

**Files:**
- Review only: all files changed in Tasks 1–3.

- [x] **Step 1: Run** `just check` and resolve failures attributable to this work.
- [x] **Step 2: Build** `apyra-auth`, `apyra-events`, `apyra-cli`, and transitive distributions into a fresh temporary directory; validate isolated installs/imports with `scripts/validate_release.py`.
- [x] **Step 3: Review** the final diff for warning scope, migration clarity, secret handling, CSRF binding, generated path safety, and unrelated worktree preservation.
- [x] **Step 4: Report** test and build results; do not publish, push, or merge.
