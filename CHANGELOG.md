# Changelog

## Unreleased

- Require configured expected issuer and audience values when JWT claim verification is enabled.
- Include configured issuer and audience claims in tokens issued by `TokenService` and enforce them
  during refresh, revocation, and access-token verification.
- Missing OAuth token response `token_type` temporarily defaults to `Bearer` with a
  `DeprecationWarning`; providers must return `token_type` before the next major `apyra-auth` release.
- Incomplete custom `EventBus` subclasses remain temporarily instantiable with a
  `DeprecationWarning`; implement both `publish()` and `subscribe()` before the next major
  `apyra-events` release.
- `apyra new <name> --template cookie-auth` generates an opt-in cookie-auth integration starter
  with CSRF protection on unsafe routes; the default minimal starter is unchanged.

## 0.1.0

Initial release of the Apyra framework workspace.

### Packages

- `apyra-core`
- `apyra-fastapi`
- `apyra-db`
- `apyra-auth`
- `apyra-storage`
- `apyra-cache`
- `apyra-ai`
- `apyra-observability`
- `apyra-email`
- `apyra-channels`
- `apyra-i18n`
- `apyra-events`
- `apyra-security`
- `apyra-tasks`
- `apyra-cli`
- `apyra` (metapackage)

### Quality

- Ruff, Ruff format, MyPy, Pyright, and Pytest pass.
- All distributions build and install in isolated environments.
