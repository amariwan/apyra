# Security

Apyra supplies security primitives, not a substitute for an application threat model.

## Secure defaults and boundaries

- Validate JWT signature, issuer, audience, algorithm, expiry, and intended token type.
- Use role/scope dependencies only after authentication; enforce tenant ownership in data access too.
- Keep secrets in the deployment secret store and redact them from logs and diagnostics.
- Use HTTPS, secure cookie attributes, trusted origins, and CSRF protection for cookie authentication.
- Use parameterized database APIs and validate upload/storage paths.
- Run dependency, static, secret, and workflow scans before release.

`apyra-security` includes constant-time comparison, redaction, PBKDF2 password hashing, API-key
helpers, audit/tenant primitives, and signed CSRF tokens. CSRF secrets must contain at least 32 random
UTF-8 bytes. Bind double-submit tokens to an application-validated session value when possible.

Password verification accepts legacy hashes for compatibility. After a successful verification,
check `password_hash_needs_rehash` and replace outdated hashes.

Review the [authentication guide](authentication.md) and the repository `SECURITY.md` before
deployment. Report vulnerabilities through the private channel documented there, not a public issue.
