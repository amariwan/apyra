# apyra-fastapi

FastAPI application factory and HTTP adapters for Apyra.

## Installation

```bash
uv add apyra-fastapi
```

## Quick usage

```python
from fastapi import APIRouter

from apyra.core import Settings
from apyra.fastapi import create_app

router = APIRouter()


@router.get("/hello")
async def hello() -> dict[str, str]:
    return {"message": "Hello from Apyra"}


app = create_app(title="My API", routers=[router], settings=Settings(api_prefix="/api"))
```

## Key exports

- `create_app` — application factory with security headers, CORS, rate limiting, health check
- `get_current_token`, `get_current_user`, `require_roles`, `require_scopes`
- `cbv`, `get`, `post`, `put`, `patch`, `delete` — class-based views
- `TimingMiddleware`, `register_timing_middleware`
- `set_operation_ids`, `simplify_operation_ids`

## Rate limiting

`create_app(rate_limit_enabled=True)` uses an in-memory counter keyed by the ASGI client
address. Limits are local to each application process; they are not shared across workers or
instances. For multi-process or distributed deployments, enforce shared limits at a trusted
proxy/API gateway or use a shared rate-limit backend. When running behind a proxy, configure
trusted-proxy handling so the ASGI client address represents the intended client.

## Authentication boundaries

`get_current_token` verifies the JWT signature, issuer, audience, required claims, expiration, and
revocation state, and rejects tokens marked `type="refresh"`. It cannot infer whether an otherwise
valid JWT without a token-type marker is an OIDC ID token or an API access token. Use an API
audience distinct from the OIDC client ID, and have the trusted issuer or application enforce an
explicit access-token type before using the payload for API authorization. Apyra can require an
exact payload `type` claim by setting `AuthSettings(expected_access_token_type="access")` on
`app.state.auth_settings`, in the injected `JWTAuthenticator`, or with
`AUTH_EXPECTED_ACCESS_TOKEN_TYPE=access`; missing or different values return 401, including when an
authenticator is injected on `app.state`. It is unset by default for
compatibility. This setting checks the payload claim, not the JOSE header `typ`. Issuers following the
[RFC 9068 access-token profile](https://www.rfc-editor.org/rfc/rfc9068.html) mark access tokens with
header `typ="at+jwt"` or `typ="application/at+jwt"`; [OIDC Core ID-token validation](https://openid.net/specs/openid-connect-core-1_0.html#IDTokenValidation)
uses the registered client ID as an audience.

To require the JOSE marker, configure `AuthSettings(expected_access_token_header_typ="at+jwt")`
or `AUTH_EXPECTED_ACCESS_TOKEN_HEADER_TYP=at+jwt`. This check also applies when an authenticator
is injected on `app.state`; it remains unset by default for compatibility. Configure the exact
value emitted by the trusted issuer.

`get_current_token` also accepts the configured access-token cookie when no bearer credential is
provided. Set `AuthSettings(access_token_cookie=None)` to disable cookie fallback and require bearer
credentials. Cookie authentication validates the token but does not check a CSRF token or the request
`Origin`. Do not use
cookie fallback to protect state-changing routes without an application-owned CSRF defense, such as
a CSRF token check and trusted-origin validation. Cookie attributes such as `Secure`, `HttpOnly`,
and an appropriate `SameSite` policy are configured by the application that issues the cookie;
they do not replace request-integrity checks when cross-site cookie transmission is allowed.

FastAPI routes can use Apyra's signed double-submit dependency:

    from fastapi import APIRouter, Depends

    from apyra.fastapi import require_csrf
    from apyra.security import generate_csrf_token

    csrf_dependency = require_csrf(
        secret=csrf_secret,
        binding_cookie_name="session_id",
    )
    router = APIRouter(dependencies=[Depends(csrf_dependency)])

For a login route without an established session binding, create a separate dependency
without binding_cookie_name. Use the session-bound dependency for authenticated state changes.

When establishing a session, issue a token bound to the validated session ID:

    csrf_token = generate_csrf_token(csrf_secret, binding=session_id)
    response.set_cookie(
        "csrf_token",
        csrf_token,
        secure=True,
        httponly=False,
        samesite="lax",
    )

Every unsafe request to a route using this dependency, including unauthenticated actions such as
login, must include the signed token as a script-readable csrf_token cookie and send the same value
in X-CSRF-Token. For authenticated sessions, the configured binding cookie must contain the same
application-validated session value used when generating the token. Only safe methods bypass the
check; every unsafe request on an opted-in route must include a valid token, including requests
with Bearer credentials. Authentication and authorization still need their own route dependencies.
This dependency does not validate Origin; add trusted-origin validation where required by the
deployment.

## Documentation

See [`examples/minimal-api`](https://github.com/amariwan/apyra/tree/main/examples/minimal-api) and
[`examples/authenticated-api`](https://github.com/amariwan/apyra/tree/main/examples/authenticated-api).

## License

MIT
