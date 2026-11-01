# Authentication

`apyra-auth` validates JWT access tokens with either remote JWKS keys or an explicit HMAC secret.
`apyra-fastapi` exposes request dependencies such as `get_current_token`, `get_current_user`,
`require_roles`, and `require_scopes`.

## Production: asymmetric issuer keys

```python
from apyra.auth import AuthSettings

settings = AuthSettings(
    mode="jwks",
    jwks_url="https://identity.example/.well-known/jwks.json",
    issuer="https://identity.example/",
    audience="orders-api",
    algorithms=["RS256"],
    expected_access_token_type="access",
)

app.state.auth_settings = settings
```

Use an API audience distinct from an OIDC client ID. Configure the exact token-type claims and JOSE
header values emitted by the trusted issuer; compatibility defaults do not prove that a valid JWT is
an API access token.

## Local automated tests: HMAC

```python
from pydantic import SecretStr

from apyra.auth import AuthSettings

app.state.auth_settings = AuthSettings(
    mode="hs",
    hs_secret=SecretStr("replace-with-a-long-random-test-secret"),
    issuer="apyra-test",
    audience="apyra-test-api",
    algorithms=["HS256"],
)
```

HMAC mode is useful for isolated tests. Do not hard-code a production secret or share one across
unrelated services.

## Cookie boundary

Cookie fallback validates the token but does not by itself validate CSRF or request origin. For
state-changing routes, configure secure cookie attributes, trusted origins, HTTPS, and Apyra's CSRF
dependency or an equivalent application-owned defense. See the [security guide](security.md).
