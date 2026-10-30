import time

import jwt
import pytest
from pydantic import SecretStr

from apyra.auth import AuthenticationError, AuthSettings, JWTAuthenticator, extract_roles


def _token(secret: str, **claims: object) -> str:
    payload = {
        "sub": "user-1",
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
        "roles": ["read"],
    }
    payload.update(claims)
    return jwt.encode(payload, secret, algorithm="HS256")


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


def test_invalid_signature_rejected() -> None:
    settings = AuthSettings(
        mode="hs", hs_secret=SecretStr("secret-a"), algorithms=["HS256"], issuer=None, audience=None
    )
    token = _token("secret-b")
    with pytest.raises(AuthenticationError):
        JWTAuthenticator(settings).decode_token(token)


def test_expired_token_rejected() -> None:
    secret = "secret"
    settings = AuthSettings(
        mode="hs", hs_secret=SecretStr(secret), algorithms=["HS256"], issuer=None, audience=None
    )
    token = jwt.encode({"sub": "u", "iat": 1, "exp": 2, "roles": []}, secret, algorithm="HS256")
    with pytest.raises(AuthenticationError):
        JWTAuthenticator(settings).decode_token(token)


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
        issuer=None,
        audience=None,
    )
    with pytest.raises(AuthenticationError):
        JWTAuthenticator(settings).decode_token(token)
