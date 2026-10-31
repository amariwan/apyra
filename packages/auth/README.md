# apyra-auth

JWT, OAuth2/OIDC, RBAC, and authorization policies for Apyra.

## Installation

```bash
uv add apyra-auth
```

## Quick usage

```python
from pydantic import SecretStr

from apyra.auth import AuthSettings, JWTAuthenticator, TokenService

settings = AuthSettings(
    mode="hs",
    hs_secret=SecretStr("replace-with-a-strong-secret"),
    algorithms=["HS256"],
    issuer="my-api",
    audience="my-api-clients",
)
service = TokenService(settings)
pair = service.issue_token_pair("user-1", scopes=["read"])
print(pair.access_token)
```

## Key exports

- `AuthSettings`, `get_auth_settings`
- `JWTAuthenticator`, `get_jwt_authenticator`
- `TokenService` / `TokenIssuer`, `TokenPair`
- `RevocationStore`, `InMemoryRevocationStore`
- `Policy`, `PolicyEngine`, `RolePolicy`, `ScopePolicy`, `AllOfPolicy`, `AnyOfPolicy`
- `OAuth2Client`, `OIDCClient`, `discover_oidc`

## Security notes

- Signature verification is mandatory and cannot be disabled.
- JWT expiration verification is mandatory; `JWTAuthenticator` rejects `verify_exp=False`.
- JWTs are validated for `sub`, `iat`, and `exp` claims.
- Issuer and audience verification are enabled by default and require configured expected values.
- When using FastAPI's `get_current_token`, set `AuthSettings(expected_access_token_type="access")` (or `AUTH_EXPECTED_ACCESS_TOKEN_TYPE=access`) to require an exact payload `type` claim. `JWTAuthenticator.decode_access_token()` enforces this API-specific setting; generic `decode_token()` remains profile-neutral for OIDC ID tokens. It is unset by default for compatibility with untyped access tokens.
- For issuers that follow RFC 9068, also set `AuthSettings(expected_access_token_header_typ="at+jwt")` (or `AUTH_EXPECTED_ACCESS_TOKEN_HEADER_TYP=at+jwt`) to require the JOSE header marker. Use `application/at+jwt` when that is the issuer's exact header value. This independent check is also unset by default for compatibility.
- JWKS is always fetched over verified TLS.
- OAuth/OIDC callers must bind a random `state` to the browser session and compare it on callback. Use PKCE and, for OIDC, a per-request nonce; persist them with the state and pass the verifier and expected nonce to `exchange_code`.
- Refresh-token reuse is consumed atomically by `InMemoryRevocationStore`. It tracks the maximum expiry of every issued access and refresh token in a family, so reuse or explicit refresh-token revocation keeps that family blocked until no linked token can remain valid. Existing custom `RevocationStore` implementations without `consume_refresh_token` remain supported and are serialized within one `TokenService`; that fallback does not coordinate multiple service instances or workers. Custom stores can expose `register_family_token_expiration(family_id, expires_at)` alongside timed consume/revoke operations to coordinate bounded cleanup. Stores without that capability must retain family revocations until their own cleanup policy confirms no linked token remains valid. Shared deployments should provide atomic consumption and family-expiry tracking across workers.

## Configuration migration

- When `verify_iss` or `verify_aud` is enabled, configure the corresponding `issuer` or `audience`; authentication now fails closed when an expected value is missing. Existing deployments must supply these values before upgrading.
- `JWTAuthenticator` requires custom revocation stores to implement both `is_revoked(jti)` and `is_family_revoked(family_id)`. Stores that previously omitted either method must implement the check before upgrading.
- Expiration verification cannot be disabled. HS mode accepts HMAC algorithms only.
- OAuth token endpoint success responses must include a non-empty string `access_token` and should include a non-empty string `token_type`. A missing `token_type` temporarily defaults to `Bearer` with a `DeprecationWarning`; correct the provider response before the next major `apyra-auth` release. Empty or wrong-typed values remain errors.
- `OIDCClient.userinfo()` now requires `expected_subject` from a cryptographically validated ID Token and rejects UserInfo responses whose `sub` is missing, non-string, or different. Callers must configure an authenticator to validate the ID Token before using its subject; this is a public API change.

## OAuth/OIDC authorization code flow

Keep the state, PKCE verifier, and OIDC nonce in the user's server-side session until the callback is validated. Compare the returned state before exchanging the code.

```python
import secrets

from apyra.auth import AuthSettings, JWTAuthenticator, OIDCClient, generate_pkce_pair

issuer = "https://issuer.example"
client = OIDCClient(
    issuer=issuer,
    client_id="client-id",
    authenticator=JWTAuthenticator(
        AuthSettings(
            mode="jwks",
            jwks_url=f"{issuer}/.well-known/jwks.json",
            issuer=issuer,
            audience="client-id",
        )
    ),
)

state = secrets.token_urlsafe(32)
nonce = secrets.token_urlsafe(32)
verifier, challenge = generate_pkce_pair()

# Save state, nonce, and verifier in the session associated with this browser.
authorization_url = await client.authorization_url(
    state=state,
    nonce=nonce,
    code_challenge=challenge,
)

# On callback, reject a state mismatch before doing the token exchange.
tokens, id_token = await client.exchange_code(
    code,
    code_verifier=verifier,
    expected_nonce=nonce,
)

if id_token is None:
    raise RuntimeError("A validated ID Token is required before requesting UserInfo")
profile = await client.userinfo(
    tokens.access_token,
    expected_subject=id_token["payload"]["sub"],
)
```

Configure `OIDCClient` with a `JWTAuthenticator` to validate returned ID tokens. `OIDCClient` does not persist browser state or PKCE values itself; the application owns that session boundary.

## License

MIT
