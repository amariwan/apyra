# apyra-security

Security primitives for Apyra.

## Purpose

`apyra-security` provides password hashing, API key generation/verification, CSRF token generation/verification, constant-time comparison, and redaction helpers.

## Installation

```bash
uv add apyra-security
```

## Minimal usage

```python
from apyra.security import hash_password, verify_password

hashed = hash_password("secret")
assert verify_password("secret", hashed)
```

## Optional dependencies

None.

## Configuration

No central settings; functions accept explicit parameters.

## Public API

- `hash_password`, `verify_password`, `password_hash_needs_rehash`
- `generate_api_key`, `verify_api_key`
- `generate_csrf_token`, `verify_csrf_token`
- `constant_time_compare`
- `redact_mapping`
- `TenantContext`, `TenantResolver`, `require_tenant`
- `get_current_tenant`, `set_current_tenant`, `reset_current_tenant` (request-scoped tenant context)

## Multi-tenancy

`apyra-security` provides the tenant *context* primitives; combine them with
`TenantScopedMixin` and `TenantScopedRepository` from `apyra-db` for fail-closed,
tenant-scoped data access:

```python
from apyra.security import TenantContext, set_current_tenant, reset_current_tenant

token = set_current_tenant(TenantContext(tenant_id="tenant-a"))
try:
    # ... request handling; repositories resolve the tenant from context ...
finally:
    reset_current_tenant(token)
```

## Error behavior

Verification functions return booleans rather than raising on mismatch. Invalid inputs raise `ValueError`/`TypeError`.

## Integration

Used by `apyra-fastapi` (CSRF dependency) and application code.

## Compatibility

- Python ≥ 3.12
- Depends on `apyra-core>=0.1.0,<0.2.0`

## License

MIT
