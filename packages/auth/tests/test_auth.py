import base64
import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from typing import Any, cast

import jwt
import pytest
from pydantic import HttpUrl, SecretStr, TypeAdapter

from apyra.auth import (
    AuthenticationError,
    AuthSettings,
    JWTAuthenticator,
    extract_roles,
    get_jwt_authenticator,
    reset_jwt_authenticator,
)


def _token(secret: str, **claims: object) -> str:
    payload: dict[str, object] = {
        "sub": "user-1",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "roles": ["read"],
    }
    payload.update(claims)
    return jwt.encode(payload, secret, algorithm="HS256")


def _token_without_header_typ(secret: str) -> str:
    header = {"alg": "HS256"}
    payload = {"sub": "user-1", "iat": int(time.time()), "exp": int(time.time()) + 3600}
    encoded_header = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=")
    encoded_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
    signing_input = encoded_header + b"." + encoded_payload
    signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=")
    return b".".join((encoded_header, encoded_payload, encoded_signature)).decode()


def test_auth_settings_repr_redacts_credentials_embedded_in_provider_urls() -> None:
    settings = AuthSettings.model_validate(
        {
            "jwks_url": "https://user:jwks-secret@issuer.example/jwks",
            "oidc_discovery_url": "https://user:oidc-secret@issuer.example/.well-known/openid-configuration",
            "oauth2_introspection_url": "https://user:introspection-secret@issuer.example/introspect",
        }
    )

    representation = repr(settings)

    assert "jwks-secret" not in representation
    assert "oidc-secret" not in representation
    assert "introspection-secret" not in representation
    assert "jwks-secret" in str(settings.jwks_url)


def test_hs256_valid_token() -> None:
    secret = "super-secret-key-with-enough-length"
    settings = AuthSettings(
        mode="hs", hs_secret=SecretStr(secret), issuer="iss", audience="aud", algorithms=["HS256"]
    )
    authenticator = JWTAuthenticator(settings)
    token = _token(secret, iss="iss", aud="aud")
    decoded = authenticator.decode_token(token)
    assert decoded["payload"]["sub"] == "user-1"
    assert extract_roles(decoded["payload"]) == {"read"}


def test_expected_access_token_type_can_be_set_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_EXPECTED_ACCESS_TOKEN_TYPE", "access")

    settings = AuthSettings()

    assert settings.expected_access_token_type == "access"


def test_expected_access_token_header_typ_can_be_set_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_EXPECTED_ACCESS_TOKEN_HEADER_TYP", "at+jwt")

    settings = AuthSettings()

    assert settings.expected_access_token_header_typ == "at+jwt"


def test_jwt_authenticator_can_require_an_access_token_type() -> None:
    secret = "secret-with-enough-length-for-hs256"
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr(secret),
        algorithms=["HS256"],
        verify_iss=False,
        verify_aud=False,
        expected_access_token_type="access",
    )
    authenticator = JWTAuthenticator(settings)

    with pytest.raises(AuthenticationError, match="token_type_invalid"):
        authenticator.decode_access_token(_token(secret))

    decoded = authenticator.decode_access_token(_token(secret, type="access"))

    assert decoded["payload"]["type"] == "access"


def test_jwt_authenticator_can_require_an_access_token_header_typ() -> None:
    secret = "secret-with-enough-length-for-hs256"
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr(secret),
        algorithms=["HS256"],
        verify_iss=False,
        verify_aud=False,
        expected_access_token_type="access",
        expected_access_token_header_typ="at+jwt",
    )
    authenticator = JWTAuthenticator(settings)
    payload = {
        "sub": "user-1",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "type": "access",
    }
    ordinary_jwt = jwt.encode(payload, secret, algorithm="HS256", headers={"typ": "JWT"})
    access_token = jwt.encode(payload, secret, algorithm="HS256", headers={"typ": "at+jwt"})

    with pytest.raises(AuthenticationError, match="token_header_type_invalid"):
        authenticator.decode_access_token(ordinary_jwt)

    assert authenticator.decode_access_token(access_token)["header"].get("typ") == "at+jwt"


def test_jwt_authenticator_rejects_missing_configured_header_typ() -> None:
    secret = "secret-with-enough-length-for-hs256"
    token = _token_without_header_typ(secret)
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr(secret),
        algorithms=["HS256"],
        verify_iss=False,
        verify_aud=False,
        expected_access_token_header_typ="JWT",
    )

    with pytest.raises(AuthenticationError, match="token_header_type_invalid"):
        JWTAuthenticator(settings).decode_access_token(token)

    compatible_settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr(secret),
        algorithms=["HS256"],
        verify_iss=False,
        verify_aud=False,
    )
    decoded = JWTAuthenticator(compatible_settings).decode_token(token)
    assert decoded["header"].get("typ") == "JWT"


@pytest.mark.parametrize("algorithms", ["HS256", "HS256, HS384"])
def test_hs256_accepts_string_algorithm_setting(algorithms: str) -> None:
    secret = "secret-with-enough-length-for-hs256"
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr(secret),
        algorithms=algorithms,
        verify_iss=False,
        verify_aud=False,
    )

    decoded = JWTAuthenticator(settings).decode_token(_token(secret))

    assert decoded["payload"]["sub"] == "user-1"


def test_hs_mode_rejects_non_hmac_algorithm() -> None:
    secret = "secret-with-enough-length-for-hs256"
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr(secret),
        algorithms=["HS256", "RS256"],
        verify_iss=False,
        verify_aud=False,
    )

    with pytest.raises(AuthenticationError, match="algorithm_invalid"):
        JWTAuthenticator(settings).decode_token(_token(secret))


def test_jwt_authenticator_rejects_incomplete_revocation_store() -> None:
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr("secret-with-enough-length-for-hs256"),
        algorithms=["HS256"],
        verify_iss=False,
        verify_aud=False,
    )

    def is_revoked(_jti: str) -> bool:
        return False

    incomplete_store = SimpleNamespace(is_revoked=is_revoked)

    with pytest.raises(
        TypeError,
        match="revocation_store must implement is_revoked and is_family_revoked",
    ):
        JWTAuthenticator(settings, revocation_store=cast(Any, incomplete_store))


def test_issuer_verification_requires_expected_issuer() -> None:
    secret = "secret-with-enough-length-for-hs256"
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr(secret),
        algorithms=["HS256"],
        issuer=None,
        audience="apyra-api",
    )

    with pytest.raises(AuthenticationError, match="issuer_required"):
        JWTAuthenticator(settings).decode_token(_token(secret, aud="apyra-api"))


def test_audience_verification_requires_expected_audience() -> None:
    secret = "secret-with-enough-length-for-hs256"
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr(secret),
        algorithms=["HS256"],
        issuer="apyra",
        audience=None,
    )

    with pytest.raises(AuthenticationError, match="audience_required"):
        JWTAuthenticator(settings).decode_token(_token(secret, iss="apyra"))


def test_jwks_authenticator_uses_injected_settings_url(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = AuthSettings(
        mode="jwks",
        algorithms=["RS256"],
        jwks_url=TypeAdapter(HttpUrl).validate_python(
            "https://issuer.example/.well-known/jwks.json"
        ),
        issuer="https://issuer.example",
        audience="apyra-api",
    )
    requested_urls: list[str] = []

    def get_client(url: str) -> SimpleNamespace:
        requested_urls.append(url)

        def fail_lookup(_token: str) -> None:
            raise jwt.PyJWKClientError("unknown kid")

        return SimpleNamespace(get_signing_key_from_jwt=fail_lookup)

    monkeypatch.setattr("apyra.auth.jwt.get_jwks_client", get_client)
    token = jwt.encode(
        {"sub": "user-1"}, "test-secret-that-is-long-enough-for-hs256", algorithm="HS256"
    )

    with pytest.raises(AuthenticationError, match="jwks_unavailable"):
        JWTAuthenticator(settings).decode_token(token)

    assert requested_urls == [str(settings.jwks_url)]


def test_jwks_invalid_key_set_maps_to_authentication_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = AuthSettings(
        mode="jwks",
        algorithms=["RS256"],
        jwks_url=TypeAdapter(HttpUrl).validate_python("https://issuer.example/jwks"),
        issuer="https://issuer.example",
        audience="apyra-api",
    )

    def get_client(_url: str) -> SimpleNamespace:
        def fail_lookup(_token: str) -> None:
            raise jwt.PyJWKSetError("invalid JWKS document")

        return SimpleNamespace(get_signing_key_from_jwt=fail_lookup)

    monkeypatch.setattr("apyra.auth.jwt.get_jwks_client", get_client)

    def get_unverified_header(_token: str) -> dict[str, str]:
        return {"alg": "RS256"}

    monkeypatch.setattr("apyra.auth.jwt.jwt.get_unverified_header", get_unverified_header)
    with pytest.raises(AuthenticationError, match="jwks_unavailable"):
        JWTAuthenticator(settings).decode_token("synthetic-token")


def test_jwks_authenticator_rejects_plaintext_url() -> None:
    settings = AuthSettings(
        mode="jwks",
        algorithms=["RS256"],
        jwks_url=TypeAdapter(HttpUrl).validate_python(
            "http://issuer.example/.well-known/jwks.json"
        ),
        issuer="http://issuer.example",
        audience="apyra-api",
    )

    with pytest.raises(AuthenticationError, match="jwks_https_required"):
        JWTAuthenticator(settings).decode_token("not-a-jwt")


def test_jwks_authenticator_rejects_url_userinfo() -> None:
    settings = AuthSettings(
        mode="jwks",
        algorithms=["RS256"],
        jwks_url=TypeAdapter(HttpUrl).validate_python("https://client:secret@issuer.example/jwks"),
        issuer="https://issuer.example",
        audience="apyra-api",
    )

    with pytest.raises(AuthenticationError, match="jwks_url_userinfo_forbidden"):
        JWTAuthenticator(settings).decode_token("not-a-jwt")


def test_invalid_signature_rejected() -> None:
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr("secret-a-that-is-long-enough-for-hs256"),
        algorithms=["HS256"],
        issuer=None,
        audience=None,
        verify_iss=False,
        verify_aud=False,
    )
    token = _token("secret-b-that-is-long-enough-for-hs256")
    with pytest.raises(AuthenticationError):
        JWTAuthenticator(settings).decode_token(token)


def test_expired_token_rejected() -> None:
    secret = "expired-token-test-secret-long-enough-for-hs256"
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr(secret),
        algorithms=["HS256"],
        issuer=None,
        audience=None,
        verify_iss=False,
        verify_aud=False,
    )
    token = jwt.encode({"sub": "u", "iat": 1, "exp": 2, "roles": []}, secret, algorithm="HS256")
    with pytest.raises(AuthenticationError):
        JWTAuthenticator(settings).decode_token(token)


def test_jwt_authenticator_rejects_disabled_expiration_verification() -> None:
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr("secret-with-enough-length-for-hs256"),
        algorithms=["HS256"],
        verify_exp=False,
        verify_iss=False,
        verify_aud=False,
    )

    with pytest.raises(AuthenticationError, match="expiration_verification_required"):
        JWTAuthenticator(settings).decode_token(_token("secret-with-enough-length-for-hs256"))


def test_alg_none_rejected() -> None:
    import base64
    import json

    def b64(value: dict[str, object]) -> bytes:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=")

    header = b64({"alg": "none", "typ": "JWT"})
    payload = b64({"sub": "u", "roles": []})
    token = (header + b"." + payload + b".").decode()
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr("secret"),
        algorithms=["HS256"],
        issuer=None,
        audience=None,
        verify_iss=False,
        verify_aud=False,
    )
    with pytest.raises(AuthenticationError, match="alg_none_forbidden"):
        JWTAuthenticator(settings).decode_token(token)


@pytest.mark.parametrize(
    ("error_type", "expected_error"),
    [
        (jwt.ExpiredSignatureError, "token_expired"),
        (jwt.InvalidAudienceError, "token_audience_invalid"),
        (jwt.InvalidIssuerError, "token_issuer_invalid"),
        (jwt.InvalidSignatureError, "token_signature_invalid"),
        (jwt.DecodeError, "invalid_token"),
    ],
)
def test_hs_jwt_decode_errors_map_to_authentication_errors(
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[Exception],
    expected_error: str,
) -> None:
    secret = "secret-with-enough-length-for-hs256"
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr(secret),
        algorithms=["HS256"],
        verify_iss=False,
        verify_aud=False,
    )

    def fail_decode(*_args: Any, **_kwargs: Any) -> None:
        raise error_type("provider error")

    monkeypatch.setattr("apyra.auth.jwt.jwt.decode", fail_decode)
    with pytest.raises(AuthenticationError, match=expected_error):
        JWTAuthenticator(settings).decode_token(_token(secret))


def test_malformed_jwt_header_maps_to_authentication_error() -> None:
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr("secret-with-enough-length-for-hs256"),
        algorithms=["HS256"],
        verify_iss=False,
        verify_aud=False,
    )

    with pytest.raises(AuthenticationError, match="invalid_header"):
        JWTAuthenticator(settings).decode_token("not-a-jwt")


@pytest.mark.parametrize(
    ("error_type", "expected_error"),
    [
        (jwt.ExpiredSignatureError, "token_expired"),
        (jwt.InvalidAudienceError, "token_audience_invalid"),
        (jwt.InvalidIssuerError, "token_issuer_invalid"),
        (jwt.InvalidSignatureError, "token_signature_invalid"),
        (jwt.DecodeError, "invalid_token"),
    ],
)
def test_jwks_decode_errors_map_to_authentication_errors(
    monkeypatch: pytest.MonkeyPatch,
    error_type: type[Exception],
    expected_error: str,
) -> None:
    settings = AuthSettings(
        mode="jwks",
        jwks_url=TypeAdapter(HttpUrl).validate_python("https://issuer.example/jwks"),
        algorithms=["RS256"],
        issuer="https://issuer.example",
        audience="apyra-api",
    )

    class SigningKey:
        key = "test-public-key"

    class JwksClient:
        def get_signing_key_from_jwt(self, _token: str) -> SigningKey:
            return SigningKey()

    def get_jwks_client(_url: HttpUrl) -> JwksClient:
        return JwksClient()

    monkeypatch.setattr("apyra.auth.jwt.get_jwks_client", get_jwks_client)

    def fail_decode(*_args: Any, **_kwargs: Any) -> None:
        raise error_type("provider error")

    monkeypatch.setattr("apyra.auth.jwt.jwt.decode", fail_decode)
    with pytest.raises(AuthenticationError, match=expected_error):
        JWTAuthenticator(settings).decode_token(_token("test-secret-with-enough-length-for-jwks"))


@pytest.mark.parametrize(
    ("settings", "expected_error"),
    [
        (
            AuthSettings(
                mode="hs",
                hs_secret=SecretStr("secret-with-enough-length-for-hs256"),
                algorithms=["HS256"],
                verify_signature=False,
                verify_iss=False,
                verify_aud=False,
            ),
            "signature_verification_required",
        ),
        (
            AuthSettings(
                mode="hs",
                hs_secret=SecretStr("secret-with-enough-length-for-hs256"),
                algorithms=[],
                verify_iss=False,
                verify_aud=False,
            ),
            "algorithms_required",
        ),
        (
            AuthSettings(
                mode="hs",
                hs_secret=SecretStr("secret-with-enough-length-for-hs256"),
                algorithms=["none"],
                verify_iss=False,
                verify_aud=False,
            ),
            "algorithm_invalid",
        ),
        (
            AuthSettings(
                mode="jwks",
                algorithms=["RS256"],
                issuer=None,
                audience=None,
                verify_iss=False,
                verify_aud=False,
            ),
            "jwks_url_missing",
        ),
        (
            AuthSettings(
                mode="jwks",
                jwks_url=TypeAdapter(HttpUrl).validate_python("https://issuer.example/jwks"),
                algorithms=["HS256"],
                issuer=None,
                audience=None,
                verify_iss=False,
                verify_aud=False,
            ),
            "algorithm_invalid",
        ),
        (
            AuthSettings(
                mode="hs",
                hs_secret=None,
                algorithms=["HS256"],
                verify_iss=False,
                verify_aud=False,
            ),
            "auth_hs_secret_missing",
        ),
    ],
)
def test_jwt_authenticator_rejects_invalid_security_configuration(
    settings: AuthSettings,
    expected_error: str,
) -> None:
    with pytest.raises(AuthenticationError, match=expected_error):
        JWTAuthenticator(settings).decode_token("not-a-jwt")


@pytest.mark.parametrize(
    ("revoked_jtis", "revoked_families", "should_reject"),
    [
        (set[str](), set[str](), False),
        ({"token-1"}, set[str](), True),
        (set[str](), {"family-1"}, True),
    ],
)
def test_jwt_authenticator_checks_token_and_family_revocation(
    revoked_jtis: set[str],
    revoked_families: set[str],
    should_reject: bool,
) -> None:
    secret = "secret-with-enough-length-for-hs256"
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr(secret),
        algorithms=["HS256"],
        verify_iss=False,
        verify_aud=False,
    )
    token_checks: list[str] = []
    family_checks: list[str] = []

    class RevocationStore:
        def is_revoked(self, jti: str) -> bool:
            token_checks.append(jti)
            return jti in revoked_jtis

        def is_family_revoked(self, family_id: str) -> bool:
            family_checks.append(family_id)
            return family_id in revoked_families

    store = RevocationStore()

    if should_reject:
        with pytest.raises(AuthenticationError, match="token_revoked"):
            JWTAuthenticator(settings, revocation_store=store).decode_token(
                _token(secret, jti="token-1", family="family-1")
            )
    else:
        JWTAuthenticator(settings, revocation_store=store).decode_token(
            _token(secret, jti="token-1", family="family-1")
        )

    assert token_checks == ["token-1"]
    assert family_checks == ([] if revoked_jtis else ["family-1"])


def test_mutated_auth_mode_is_rejected_before_token_parsing() -> None:
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr("secret-with-enough-length-for-hs256"),
        algorithms=["HS256"],
        verify_iss=False,
        verify_aud=False,
    )
    cast(Any, settings).mode = "invalid"

    with pytest.raises(AuthenticationError, match="auth_mode_invalid"):
        JWTAuthenticator(settings).decode_token("not-a-jwt")


def test_jwt_authenticator_cache_can_be_reset() -> None:
    reset_jwt_authenticator()
    first = get_jwt_authenticator()
    assert get_jwt_authenticator() is first

    reset_jwt_authenticator()
    assert get_jwt_authenticator() is not first
    reset_jwt_authenticator()
