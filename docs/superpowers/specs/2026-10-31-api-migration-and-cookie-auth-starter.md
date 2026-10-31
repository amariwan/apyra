# API Migration and Cookie-Auth Starter Design

## Status

Approved 2026-10-31. Implementation and verification completed; final code review recorded in the task ledger.

## Context

The principal engineering audit found consumer-visible API changes in the current worktree. Some existing behavior can be retained temporarily without weakening security: accepting a missing OAuth `token_type` by normalizing it to `Bearer`, and allowing incomplete downstream `EventBus` subclasses to instantiate before their missing methods fail when used. Other changes enforce security invariants and must remain strict, including binding OIDC UserInfo to a verified ID Token subject, JWT issuer/audience/expiration validation, complete revocation checks, HTTPS identity-provider endpoints, and preventing server-wide Memcached flushes by default.

The existing `apyra new` command creates a minimal health-only FastAPI app. The library exposes `require_csrf()` and `generate_csrf_token()`, but applications must currently wire token issuance and protection themselves. The CLI has no cookie-auth starter.

## Decisions

1. **Stage safe API migrations per surface.** Preserve compatibility for the OAuth token-response missing-`token_type` case and incomplete `EventBus` subclasses with a `DeprecationWarning`. Removal or abstract enforcement may occur no earlier than the next major release of the affected distribution. Any present but empty or wrong-typed token type remains an error.
2. **Keep security invariants immediate.** Do not provide insecure compatibility fallbacks for missing or mismatched verified OIDC subjects, disabled JWT expiration checks, missing issuer/audience configuration, incomplete revocation stores, insecure identity-provider transport, or unsafe server-wide cache clearing. Document their migration requirements and rationale.
3. **Add an opt-in cookie-auth integration starter.** `apyra new <name> --template cookie-auth` creates a starter that expects an external authentication component to issue a validated `access_token` cookie. It exposes a CSRF-token bootstrap endpoint bound to that cookie and protects unsafe example routes with `require_csrf`. It does not invent a login provider, user store, or token issuer.
4. **Keep the default starter unchanged.** `apyra new <name>` remains a minimal Bearer/no-auth health app and does not acquire CSRF behavior. The CSRF secret is read from `APYRA_CSRF_SECRET`, must be at least 32 UTF-8 bytes, and the generated app fails fast if it is absent or too short. The generated CSRF cookie is script-readable, `SameSite=Lax`, and `Secure` by default. Only the explicit `APYRA_COOKIE_SECURE=false` setting disables `Secure` for local HTTP development; generated documentation warns against using that setting in production.
5. **Document compatibility and migration.** Update package docs and the changelog with each warning, the safe migration path, the security exceptions, and the earliest removal milestone. Do not announce a specific release number or perform a release.

## Behavior and interfaces

- On OAuth token responses with no `token_type`, `_token_request()` returns `OAuth2TokenResponse(token_type="Bearer")` and emits `DeprecationWarning` at the caller-facing stack level. Empty or non-string `token_type` values still fail validation.
- `EventBus` methods temporarily remain concrete methods that raise `NotImplementedError`. An incomplete downstream subclass emits one `DeprecationWarning` when defined; built-in complete adapters emit none. Making the base abstract is reserved for a major release.
- The CLI accepts `--template minimal|cookie-auth`; `minimal` is the default. Generated files are written only beneath the requested project root and retain current overwrite protection.
- The cookie-auth template validates requests with the existing Apyra auth and CSRF dependencies. Unsafe routes require a valid token in both `csrf_token` cookie and `X-CSRF-Token` header; the token is HMAC-bound to the `access_token` cookie. The starter does not claim to implement Origin checks or authentication issuance; it documents those application/provider responsibilities.

## Non-goals

- No weakening of security validation to preserve legacy behavior.
- No default CSRF middleware or changes to existing generated projects.
- No sample username/password login, token minting, user database, OAuth provider integration, or cross-origin CORS policy.
- No distribution release, publishing, version bump, PR merge, or changes outside the scoped docs, CLI generator, OAuth client, and Events base contract.

## Verification

- Unit tests prove warnings occur for the selected deprecated paths and not for valid/new paths; warning assertions pin category, message, and caller-facing stack level.
- CLI tests inspect generated files and exercise the generated app with valid, missing, mismatched, and malformed cookie/header CSRF values. They verify missing secrets fail fast and the minimal template remains unchanged.
- Focused OAuth, Events, and CLI tests pass, followed by the repository quality gates and isolated package import/release validation applicable to touched packages.
- Review the complete diff to ensure no pre-existing user changes were overwritten and no insecure compatibility fallback was added.

## Risks

- Consumers may suppress `DeprecationWarning`; release notes and explicit migration guidance are required.
- Warning at downstream subclass definition can occur during imports; tests must ensure complete built-in adapters stay quiet.
- A generated cookie-auth integration starter relies on provider/application configuration for access-token validation, cookie issuance, Origin policy, and deployment TLS. The generated README must state those prerequisites prominently.
