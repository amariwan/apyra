# apyra-security

Security primitives for Apyra (constant-time comparison, secret redaction,
password hashing, API keys, CSRF).

Password hashes use salted PBKDF2-HMAC-SHA256 with 600,000 iterations. The
verifier continues to accept legacy three-part hashes made with 390,000
iterations. After a successful `verify_password`, call
`password_hash_needs_rehash`; when it returns `True`, replace the stored value
with `hash_password(password)` to upgrade it.

## Installation

```bash
uv add apyra-security
```

CSRF helpers require a random secret of at least 32 UTF-8 bytes. Generate and
store one in application configuration, for example with
`secrets.token_urlsafe(32)`; do not use an empty, short, or hard-coded value.

For cookie-authenticated requests, bind tokens to an application-validated
session value when generating and verifying them:

```python
token = generate_csrf_token(secret, binding=session.id)
valid = verify_csrf_token(submitted_token, secret, binding=session.id)
```

The binding must be stable for the session and unavailable to an attacker in a
different session. Omitting it preserves the legacy token format, which is not
session-bound by itself; store and compare an expected token per session if a
binding value is unavailable. These helpers do not validate request origins.

## License

MIT
