import jwt
import pytest

from apyra.auth import AuthSettings, TokenService


def _settings() -> AuthSettings:
    return AuthSettings(
        mode="hs",
        hs_secret=__import__("pydantic").SecretStr("secret-with-enough-length-for-hs256"),
        algorithms=["HS256"],
    )


def test_refresh_rotation_revokes_old_token() -> None:
    service = TokenService(_settings())
    pair = service.issue_token_pair("user-1", scopes=["read"])
    rotated = service.refresh(pair.refresh_token)
    assert rotated.access_token != pair.access_token
    old = jwt.decode(
        pair.refresh_token, "secret-with-enough-length-for-hs256", algorithms=["HS256"]
    )
    assert service.store.is_revoked(str(old["jti"]))


def test_refresh_reuse_revokes_family() -> None:
    service = TokenService(_settings())
    pair = service.issue_token_pair("user-1")
    service.refresh(pair.refresh_token)
    with pytest.raises(Exception):  # noqa: B017
        service.refresh(pair.refresh_token)
    decoded = jwt.decode(
        pair.refresh_token, "secret-with-enough-length-for-hs256", algorithms=["HS256"]
    )
    assert service.store.is_family_revoked(str(decoded["family"]))


def test_revoke_access_token() -> None:
    service = TokenService(_settings())
    pair = service.issue_token_pair("user-1")
    service.revoke(pair.access_token)
    with pytest.raises(Exception):  # noqa: B017
        service.verify_access_token(pair.access_token)
