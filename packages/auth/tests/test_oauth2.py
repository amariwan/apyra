import time
import warnings
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from pydantic import SecretStr

from apyra.auth import (
    AuthenticationError,
    AuthSettings,
    JWTAuthenticator,
    OAuth2Client,
    OAuth2TokenResponse,
    OIDCTokenValidator,
    generate_pkce_pair,
)


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://user@issuer.example.com/authorize",
        "https://user:secret@issuer.example.com/authorize",
    ],
)
def test_oauth2_rejects_endpoint_user_information(endpoint: str) -> None:
    with pytest.raises(ValueError, match="cannot contain user information"):
        OAuth2Client(
            client_id="client",
            authorization_endpoint=endpoint,
            token_endpoint="https://issuer.example.com/token",
        )


@pytest.mark.parametrize(
    "parameter",
    ["response_type", "client_id", "state", "redirect_uri", "scope", "code_challenge"],
)
def test_authorization_url_rejects_reserved_parameter_overrides(parameter: str) -> None:
    client = OAuth2Client(
        client_id="client",
        authorization_endpoint="https://issuer.example.com/authorize",
        token_endpoint="https://issuer.example.com/token",
        redirect_uri="https://app.example.com/callback",
        scopes=["openid"],
    )

    with pytest.raises(ValueError, match="cannot override OAuth protocol parameters"):
        client.authorization_url(state="state-1", extra_params={parameter: "attacker"})


def test_authorization_url_accepts_provider_specific_parameters() -> None:
    client = OAuth2Client(
        client_id="client",
        authorization_endpoint="https://issuer.example.com/authorize",
        token_endpoint="https://issuer.example.com/token",
    )

    assert "prompt=login" in client.authorization_url(
        state="state-1", extra_params={"prompt": "login"}
    )


def test_authorization_url_preserves_endpoint_query_parameters() -> None:
    client = OAuth2Client(
        client_id="client",
        authorization_endpoint="https://issuer.example.com/authorize?tenant=acme",
        token_endpoint="https://issuer.example.com/token",
    )

    query = parse_qs(urlsplit(client.authorization_url(state="state-1")).query)

    assert query["tenant"] == ["acme"]
    assert query["response_type"] == ["code"]
    assert query["client_id"] == ["client"]
    assert query["state"] == ["state-1"]


def test_authorization_url_includes_pkce() -> None:
    client = OAuth2Client(
        client_id="client",
        authorization_endpoint="https://issuer.example.com/authorize",
        token_endpoint="https://issuer.example.com/token",
        redirect_uri="https://app.example.com/callback",
        scopes=["openid", "profile"],
    )
    verifier, challenge = generate_pkce_pair()
    url = client.authorization_url(state="state-1", code_challenge=challenge)
    assert "response_type=code" in url
    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url
    assert verifier != challenge


@pytest.mark.asyncio
async def test_exchange_code_and_refresh() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            import urllib.parse

            data = dict(urllib.parse.parse_qs(request.content.decode()))
            if data.get("grant_type") == ["authorization_code"]:
                return httpx.Response(
                    200,
                    json={
                        "access_token": "access-1",
                        "refresh_token": "refresh-1",
                        "token_type": "Bearer",
                    },
                )
            if data.get("grant_type") == ["refresh_token"]:
                return httpx.Response(
                    200, json={"access_token": "access-2", "token_type": "Bearer"}
                )
        return httpx.Response(404)

    client = OAuth2Client(
        client_id="client",
        client_secret="secret",
        authorization_endpoint="https://issuer.example.com/authorize",
        token_endpoint="https://issuer.example.com/token",
        transport=httpx.MockTransport(handler),
    )
    exchanged = await client.exchange_code("code-1", code_verifier="verifier")
    assert isinstance(exchanged, OAuth2TokenResponse)
    assert exchanged.access_token == "access-1"
    refreshed = await client.refresh_token("refresh-1")
    assert refreshed.access_token == "access-2"


@pytest.mark.asyncio
async def test_token_response_does_not_treat_boolean_expiry_as_integer() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"access_token": "access", "token_type": "Bearer", "expires_in": True}
        )

    client = OAuth2Client(
        client_id="client",
        authorization_endpoint="https://issuer.example.com/authorize",
        token_endpoint="https://issuer.example.com/token",
        transport=httpx.MockTransport(handler),
    )

    response = await client.client_credentials()

    assert response.expires_in is None


@pytest.mark.asyncio
async def test_client_credentials_and_revoke() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/token":
            return httpx.Response(
                200, json={"access_token": "service-token", "token_type": "Bearer"}
            )
        if request.url.path == "/revoke":
            return httpx.Response(200)
        return httpx.Response(404)

    client = OAuth2Client(
        client_id="client",
        client_secret="secret",
        authorization_endpoint="https://issuer.example.com/authorize",
        token_endpoint="https://issuer.example.com/token",
        revocation_endpoint="https://issuer.example.com/revoke",
        transport=httpx.MockTransport(handler),
    )
    token = await client.client_credentials(scope="read")
    assert token.access_token == "service-token"
    await client.revoke(token.access_token)


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [[], 42, "not-an-object"])
async def test_oauth2_token_request_rejects_non_object_json(payload: object) -> None:
    client = OAuth2Client(
        client_id="client",
        authorization_endpoint="https://issuer.example.com/authorize",
        token_endpoint="https://issuer.example.com/token",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=payload)),
    )

    with pytest.raises(TypeError, match="OAuth2 token response must be a JSON object"):
        await client.client_credentials()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({}, "access_token"),
        ({"access_token": ""}, "access_token"),
        ({"access_token": 42}, "access_token"),
        ({"access_token": "access", "token_type": ""}, "token_type"),
        ({"access_token": "access", "token_type": 42}, "token_type"),
    ],
)
async def test_oauth2_token_request_rejects_invalid_required_fields(
    payload: dict[str, object], field: str
) -> None:
    client = OAuth2Client(
        client_id="client",
        authorization_endpoint="https://issuer.example.com/authorize",
        token_endpoint="https://issuer.example.com/token",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=payload)),
    )

    with pytest.raises(ValueError, match=f"non-empty string {field}"):
        await client.client_credentials()


@pytest.mark.asyncio
async def test_oauth2_missing_token_type_defaults_to_bearer_with_deprecation_warning() -> None:
    client = OAuth2Client(
        client_id="client",
        authorization_endpoint="https://issuer.example.com/authorize",
        token_endpoint="https://issuer.example.com/token",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json={"access_token": "access"})
        ),
    )

    with pytest.warns(DeprecationWarning, match="token_type.*next major") as captured:
        response = await client.client_credentials()

    assert response.token_type == "Bearer"
    assert len(captured) == 1
    assert captured[0].filename == __file__


@pytest.mark.asyncio
async def test_oauth2_present_token_type_does_not_warn() -> None:
    client = OAuth2Client(
        client_id="client",
        authorization_endpoint="https://issuer.example.com/authorize",
        token_endpoint="https://issuer.example.com/token",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200, json={"access_token": "access", "token_type": "Bearer"}
            )
        ),
    )

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        response = await client.client_credentials()

    assert response.token_type == "Bearer"
    assert captured == []


@pytest.mark.asyncio
async def test_oidc_token_validator_checks_nonce() -> None:
    class FakeAuthenticator:
        def decode_token(self, token: str):
            return {"header": {}, "payload": {"nonce": "expected-nonce"}}

    validator = OIDCTokenValidator(FakeAuthenticator(), expected_nonce="expected-nonce")
    assert validator.validate("token")["payload"]["nonce"] == "expected-nonce"

    validator = OIDCTokenValidator(FakeAuthenticator(), expected_nonce="wrong")
    with pytest.raises(ValueError):
        validator.validate("token")


def test_oidc_token_validator_rejects_mismatched_issuer() -> None:
    class FakeAuthenticator:
        def decode_token(self, token: str):
            return {"header": {}, "payload": {"iss": "https://other.example.com"}}

    validator = OIDCTokenValidator(
        FakeAuthenticator(), expected_issuer="https://issuer.example.com"
    )

    with pytest.raises(AuthenticationError, match="token_issuer_invalid"):
        validator.validate("token")


@pytest.mark.parametrize(
    ("authorized_party", "expected_error"),
    [
        ("client-b", None),
        (None, "token_authorized_party_invalid"),
        ("client-a", "token_authorized_party_invalid"),
    ],
)
def test_oidc_token_validator_binds_multiple_audiences_to_authorized_party(
    authorized_party: str | None, expected_error: str | None
) -> None:
    class FakeAuthenticator:
        def decode_token(self, token: str):
            return {
                "header": {},
                "payload": {"aud": ["client-b", "shared-api"], "azp": authorized_party},
            }

    validator = OIDCTokenValidator(FakeAuthenticator(), expected_audience="client-b")

    if expected_error is not None:
        with pytest.raises(AuthenticationError, match=expected_error):
            validator.validate("token")
    else:
        assert validator.validate("token")["payload"]["aud"] == ["client-b", "shared-api"]


def test_oidc_id_tokens_are_not_subject_to_api_access_type_policy() -> None:
    secret = "secret-with-enough-length-for-hs256"
    settings = AuthSettings(
        mode="hs",
        hs_secret=SecretStr(secret),
        algorithms=["HS256"],
        issuer="https://issuer.example.com",
        audience="client",
        expected_access_token_type="access",
    )
    now = int(time.time())
    id_token = jwt.encode(
        {
            "sub": "user-1",
            "iat": now,
            "exp": now + 3600,
            "iss": "https://issuer.example.com",
            "aud": "client",
            "nonce": "request-nonce",
        },
        secret,
        algorithm="HS256",
    )

    decoded = OIDCTokenValidator(
        JWTAuthenticator(settings), expected_nonce="request-nonce"
    ).validate(id_token)

    assert decoded["payload"]["sub"] == "user-1"
