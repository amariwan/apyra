import httpx
import pytest

from apyra.auth import OAuth2TokenIntrospector, discover_oidc


@pytest.mark.asyncio
async def test_discover_oidc_rejects_plaintext_provider_endpoint() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "issuer": "https://issuer.example.com",
                "jwks_uri": "https://issuer.example.com/jwks",
                "token_endpoint": "http://issuer.example.com/token",
            },
        )

    with pytest.raises(ValueError, match="token_endpoint must use HTTPS"):
        await discover_oidc("https://issuer.example.com", transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_discover_oidc_rejects_plaintext_issuer_before_request() -> None:
    with pytest.raises(ValueError, match="issuer must use HTTPS"):
        await discover_oidc("http://issuer.example.com")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("issuer", "discovery_url"),
    [
        ("https://user@issuer.example.com", None),
        ("https://issuer.example.com", "https://user:secret@issuer.example.com/config"),
    ],
)
async def test_discover_oidc_rejects_user_information(
    issuer: str, discovery_url: str | None
) -> None:
    with pytest.raises(ValueError, match="cannot contain user information"):
        await discover_oidc(issuer, discovery_url=discovery_url)


@pytest.mark.asyncio
async def test_discover_oidc_reads_jwks_uri() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).endswith("/.well-known/openid-configuration")
        return httpx.Response(
            200,
            json={
                "issuer": "https://issuer.example.com",
                "jwks_uri": "https://issuer.example.com/jwks",
                "scopes_supported": ["openid", "profile"],
            },
        )

    config = await discover_oidc(
        "https://issuer.example.com", transport=httpx.MockTransport(handler)
    )
    assert config.jwks_uri == "https://issuer.example.com/jwks"
    assert config.scopes_supported == ("openid", "profile")


@pytest.mark.asyncio
async def test_oauth2_introspection() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"].startswith("Basic ")
        return httpx.Response(200, json={"active": True, "sub": "user-1"})

    introspector = OAuth2TokenIntrospector(
        client_id="client",
        client_secret="secret",
        introspection_url="https://issuer.example.com/introspect",
        transport=httpx.MockTransport(handler),
    )
    result = await introspector.introspect("token")
    assert result["active"] is True
    assert result["sub"] == "user-1"


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [[], 42, "not-an-object"])
async def test_oauth2_introspection_rejects_non_object_json(payload: object) -> None:
    introspector = OAuth2TokenIntrospector(
        client_id="client",
        client_secret="secret",
        introspection_url="https://issuer.example.com/introspect",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=payload)),
    )

    with pytest.raises(TypeError, match="introspection response must be a JSON object"):
        await introspector.introspect("token")
