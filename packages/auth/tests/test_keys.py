import pytest
from pydantic import HttpUrl, TypeAdapter

from apyra.auth import get_jwks_client, reset_jwks_client


def test_jwks_client_is_cached_per_url_and_reset() -> None:
    reset_jwks_client()
    first = get_jwks_client("https://issuer.example/jwks")
    assert get_jwks_client("https://issuer.example/jwks") is first
    assert get_jwks_client("https://other.example/jwks") is not first
    reset_jwks_client()
    assert get_jwks_client("https://issuer.example/jwks") is not first
    reset_jwks_client()


@pytest.mark.parametrize("url", ["http://issuer.example/jwks", "file:///tmp/jwks.json"])
def test_jwks_client_rejects_non_https_url(url: str) -> None:
    with pytest.raises(RuntimeError, match="must use HTTPS"):
        get_jwks_client(url)


def test_jwks_client_rejects_url_userinfo() -> None:
    with pytest.raises(RuntimeError, match="user information"):
        get_jwks_client("https://client:secret@issuer.example/jwks")


def test_jwks_client_reads_global_url_when_not_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    from apyra.auth.settings import AuthSettings

    settings = AuthSettings(
        jwks_url=TypeAdapter(HttpUrl).validate_python("https://configured.example/jwks"),
        issuer="https://configured.example",
        audience="apyra-api",
    )
    monkeypatch.setattr("apyra.auth.settings.get_auth_settings", lambda: settings)
    reset_jwks_client()

    assert get_jwks_client().uri == str(settings.jwks_url)
    reset_jwks_client()
