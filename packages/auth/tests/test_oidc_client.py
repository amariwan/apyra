import httpx
import pytest

from apyra.auth import OIDCClient


@pytest.mark.asyncio
async def test_oidc_client_flow() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": "https://issuer.example.com",
                    "authorization_endpoint": "https://issuer.example.com/authorize",
                    "token_endpoint": "https://issuer.example.com/token",
                    "userinfo_endpoint": "https://issuer.example.com/userinfo",
                    "jwks_uri": "https://issuer.example.com/jwks",
                    "revocation_endpoint": "https://issuer.example.com/revoke",
                },
            )
        if path == "/token":
            return httpx.Response(
                200, json={"access_token": "access-1", "id_token": "id-1", "token_type": "Bearer"}
            )
        if path == "/userinfo":
            assert request.headers["authorization"] == "Bearer access-1"
            return httpx.Response(200, json={"sub": "user-1"})
        if path == "/revoke":
            return httpx.Response(200)
        return httpx.Response(404)

    client = OIDCClient(
        issuer="https://issuer.example.com",
        client_id="client",
        client_secret="secret",
        redirect_uri="https://app.example.com/callback",
        transport=httpx.MockTransport(handler),
    )
    config = await client.discover()
    assert config.jwks_uri.endswith("/jwks")

    url = await client.authorization_url(state="state-1", nonce="nonce-1")
    assert "nonce=nonce-1" in url

    token_response, _decoded = await client.exchange_code("code-1")
    assert token_response.access_token == "access-1"
    assert token_response.id_token == "id-1"

    userinfo = await client.userinfo(token_response.access_token)
    assert userinfo["sub"] == "user-1"

    await client.revoke(token_response.access_token)
