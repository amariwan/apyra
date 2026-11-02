"""Security primitives for Apyra."""

from __future__ import annotations

from .api_keys import generate_api_key, verify_api_key
from .csrf import generate_csrf_token, verify_csrf_token
from .passwords import hash_password, password_hash_needs_rehash, verify_password
from .secrets import constant_time_compare, redact_mapping
from .tenancy import (
    TenantContext,
    TenantResolver,
    get_current_tenant,
    require_tenant,
    reset_current_tenant,
    set_current_tenant,
)

__all__ = [
    "TenantContext",
    "TenantResolver",
    "constant_time_compare",
    "generate_api_key",
    "generate_csrf_token",
    "get_current_tenant",
    "hash_password",
    "password_hash_needs_rehash",
    "redact_mapping",
    "require_tenant",
    "reset_current_tenant",
    "set_current_tenant",
    "verify_api_key",
    "verify_csrf_token",
    "verify_password",
]
