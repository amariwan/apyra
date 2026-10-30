import jwt
from pydantic import SecretStr

from apyra.auth import AuthSettings
from apyra.auth import TokenService as TokenIssuer


def test_token_pair_and_rotation() -> None:
    settings = AuthSettings(
        mode="hs", hs_secret=SecretStr("secret-with-enough-length-for-hs256"), algorithms=["HS256"]
    )
    issuer = TokenIssuer(settings)
    pair = issuer.issue_token_pair("user-1", scopes=["read"])
    assert pair.access_token and pair.refresh_token

    decoded_access = jwt.decode(
        pair.access_token, "secret-with-enough-length-for-hs256", algorithms=["HS256"]
    )
    assert decoded_access["type"] == "access"
    assert decoded_access["scopes"] == ["read"]

    rotated = issuer.rotate_refresh_token(pair.refresh_token)
    assert rotated.access_token and rotated.refresh_token
    old_refresh = jwt.decode(
        pair.refresh_token, "secret-with-enough-length-for-hs256", algorithms=["HS256"]
    )
    assert issuer.blocklist.is_revoked(str(old_refresh["jti"]))
