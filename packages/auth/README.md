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

settings = AuthSettings(mode="hs", hs_secret=SecretStr("change-me"), algorithms=["HS256"])
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
- JWTs are validated for `sub`, `iat`, and `exp` claims.
- JWKS is always fetched over verified TLS.

## License

MIT