# apyra-cli

Developer CLI for Apyra.

## Installation

```bash
uv add apyra-cli
```

## Project templates

The default `apyra new <name>` command creates a minimal health-only app. For an app that uses
cookie-based access tokens, generate the opt-in CSRF-protected integration starter:

```bash
apyra new my-api --template cookie-auth
```

Set `APYRA_CSRF_SECRET` to a random value of at least 32 UTF-8 bytes. Configure
`AUTH_JWKS_URL`, `AUTH_ISSUER`, and `AUTH_AUDIENCE`; an external authentication component must issue
the validated access token in the `access_token` cookie. The starter does not implement login or
token issuance. `GET /csrf` sets a script-readable CSRF cookie, and unsafe routes require the same
token in the `X-CSRF-Token` header; tokens are bound to the access-token cookie.

The CSRF cookie uses `Secure` by default. Set `APYRA_COOKIE_SECURE=false` only for local HTTP
development. Configure Origin checks, provider cookie attributes, HTTPS, and any cross-origin CORS
policy for deployment; CSRF validation does not replace those controls.

## License

MIT
