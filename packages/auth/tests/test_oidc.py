import httpx
import pytest

from apyra.auth import OAuth2TokenIntrospector, discover_oidc


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
