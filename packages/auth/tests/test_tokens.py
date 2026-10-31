import time

import jwt
import pytest
from pydantic import SecretStr

from apyra.auth import AuthenticationError, AuthSettings
from apyra.auth import TokenService as TokenIssuer


def test_token_pair_and_rotation() -> None:
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr("secret-with-enough-length-for-hs256"),
        algorithms=["HS256"],
        issuer="apyra-tests",
        audience="apyra-api",
    )
    issuer = TokenIssuer(settings)
    pair = issuer.issue_token_pair("user-1", scopes=["read"])
    assert pair.access_token and pair.refresh_token
    assert issuer.verify_access_token(pair.access_token)["sub"] == "user-1"

    decoded_access = jwt.decode(
        pair.access_token,
        "secret-with-enough-length-for-hs256",
        algorithms=["HS256"],
        issuer="apyra-tests",
        audience="apyra-api",
    )
    assert decoded_access["type"] == "access"
    assert decoded_access["scopes"] == ["read"]

    rotated = issuer.rotate_refresh_token(pair.refresh_token)
    assert rotated.access_token and rotated.refresh_token
    old_refresh = jwt.decode(
        pair.refresh_token,
        "secret-with-enough-length-for-hs256",
        algorithms=["HS256"],
        issuer="apyra-tests",
        audience="apyra-api",
    )
    assert issuer.blocklist.is_revoked(str(old_refresh["jti"]))


def test_token_service_includes_configured_issuer_and_audience() -> None:
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr("secret-with-enough-length-for-hs256"),
        algorithms=["HS256"],
        issuer="apyra",
        audience="apyra-api",
    )

    pair = TokenIssuer(settings).issue_token_pair("user-1")
    access_claims = jwt.decode(
        pair.access_token,
        "secret-with-enough-length-for-hs256",
        algorithms=["HS256"],
        issuer="apyra",
        audience="apyra-api",
    )
    refresh_claims = jwt.decode(
        pair.refresh_token,
        "secret-with-enough-length-for-hs256",
        algorithms=["HS256"],
        issuer="apyra",
        audience="apyra-api",
    )

    assert access_claims["iss"] == "apyra"
    assert access_claims["aud"] == "apyra-api"
    assert refresh_claims["iss"] == "apyra"
    assert refresh_claims["aud"] == "apyra-api"


@pytest.mark.parametrize(
    ("issuer", "audience", "error"),
    [
        (None, "apyra-api", "issuer_required"),
        ("apyra", None, "audience_required"),
    ],
)
def test_token_service_requires_expected_identity_claims(
    issuer: str | None,
    audience: str | None,
    error: str,
) -> None:
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr("secret-with-enough-length-for-hs256"),
        algorithms=["HS256"],
        issuer=issuer,
        audience=audience,
    )

    with pytest.raises(AuthenticationError, match=error):
        TokenIssuer(settings).issue_token_pair("user-1")


def test_token_service_rejects_access_tokens_without_expiration() -> None:
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr("secret-with-enough-length-for-hs256"),
        algorithms=["HS256"],
        verify_iss=False,
        verify_aud=False,
    )
    service = TokenIssuer(settings)
    token = jwt.encode(
        {"sub": "user-1", "iat": int(time.time()), "type": "access"},
        "secret-with-enough-length-for-hs256",
        algorithm="HS256",
    )

    with pytest.raises(AuthenticationError, match="invalid_token"):
        service.verify_access_token(token)
