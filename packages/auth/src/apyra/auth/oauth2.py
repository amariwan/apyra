"""OAuth2 and OpenID Connect client helpers."""

from __future__ import annotations

import base64
import hashlib
import secrets
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from .exceptions import AuthenticationError

if TYPE_CHECKING:
    from .oidc import OIDCConfiguration
from urllib.parse import urlencode, urlsplit, urlunsplit

if TYPE_CHECKING:
    import httpx

_RESERVED_AUTHORIZATION_PARAMS = frozenset(
    {
        "response_type",
        "client_id",
        "state",
        "redirect_uri",
        "scope",
        "code_challenge",
        "code_challenge_method",
    }
)


def _empty_object_dict() -> dict[str, Any]:
    return {}


@dataclass(frozen=True, slots=True)
class OAuth2TokenResponse:
    """Token endpoint response with normalized fields and the raw payload."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
    refresh_token: str | None = None
    id_token: str | None = None
    scope: str | None = None
    raw: dict[str, Any] = field(default_factory=_empty_object_dict)


def generate_pkce_pair() -> tuple[str, str]:
    """Create a high-entropy PKCE verifier and its S256 challenge."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


class OAuth2Client:
    """Small OAuth2/OIDC client for authorization-code and client-credentials flows."""

    authorization_endpoint: str
    token_endpoint: str
    revocation_endpoint: str | None
    scopes: list[str]

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str | None = None,
        authenticator: Any = None,
        authorization_endpoint: str,
        token_endpoint: str,
        revocation_endpoint: str | None = None,
        redirect_uri: str | None = None,
        scopes: list[str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.authenticator = authenticator
        self.authorization_endpoint = _https_endpoint(
            authorization_endpoint, "authorization_endpoint"
        )
        self.token_endpoint = _https_endpoint(token_endpoint, "token_endpoint")
        self.revocation_endpoint = (
            _https_endpoint(revocation_endpoint, "revocation_endpoint")
            if revocation_endpoint
            else None
        )
        self.redirect_uri = redirect_uri
        self.scopes = scopes or []
        self._transport = transport
        self._timeout = timeout_seconds

    def authorization_url(
        self,
        *,
        state: str,
        code_challenge: str | None = None,
        code_challenge_method: str = "S256",
        extra_params: dict[str, str] | None = None,
    ) -> str:
        """Build an authorization URL, rejecting extra parameters that override protocol fields."""
        params: dict[str, str] = {
            "response_type": "code",
            "client_id": self.client_id,
            "state": state,
        }
        if self.redirect_uri:
            params["redirect_uri"] = self.redirect_uri
        if self.scopes:
            params["scope"] = " ".join(self.scopes)
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = code_challenge_method
        if extra_params:
            conflicts = _RESERVED_AUTHORIZATION_PARAMS.intersection(extra_params)
            if conflicts:
                names = ", ".join(sorted(conflicts))
                raise ValueError(f"extra_params cannot override OAuth protocol parameters: {names}")
            params.update(extra_params)
        endpoint = urlsplit(self.authorization_endpoint)
        query = "&".join(part for part in (endpoint.query, urlencode(params)) if part)
        return urlunsplit((endpoint.scheme, endpoint.netloc, endpoint.path, query, ""))

    async def exchange_code(
        self, code: str, *, code_verifier: str | None = None
    ) -> OAuth2TokenResponse:
        """Exchange an authorization code, optionally proving its PKCE verifier."""
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self.client_id,
        }
        if self.redirect_uri:
            data["redirect_uri"] = self.redirect_uri
        if self.client_secret:
            data["client_secret"] = self.client_secret
        if code_verifier:
            data["code_verifier"] = code_verifier
        return await self._token_request(data)

    async def client_credentials(self, *, scope: str | None = None) -> OAuth2TokenResponse:
        """Request an access token with the OAuth2 client-credentials grant."""
        data = {"grant_type": "client_credentials", "client_id": self.client_id}
        if self.client_secret:
            data["client_secret"] = self.client_secret
        if scope:
            data["scope"] = scope
        elif self.scopes:
            data["scope"] = " ".join(self.scopes)
        return await self._token_request(data)

    async def refresh_token(
        self, refresh_token: str, *, scope: str | None = None
    ) -> OAuth2TokenResponse:
        """Exchange a refresh token for a new OAuth2 token response."""
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
        }
        if self.client_secret:
            data["client_secret"] = self.client_secret
        if scope:
            data["scope"] = scope
        return await self._token_request(data)

    async def revoke(self, token: str, *, token_type_hint: str | None = None) -> None:
        """Revoke a token when a revocation endpoint was configured."""
        if not self.revocation_endpoint:
            raise ValueError("revocation endpoint is not configured")
        data = {"token": token, "client_id": self.client_id}
        if self.client_secret:
            data["client_secret"] = self.client_secret
        if token_type_hint:
            data["token_type_hint"] = token_type_hint
        import httpx

        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.post(self.revocation_endpoint, data=data)
            response.raise_for_status()

    async def _token_request(self, data: dict[str, str]) -> OAuth2TokenResponse:
        import httpx

        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.post(self.token_endpoint, data=data)
            response.raise_for_status()
            raw: object = response.json()
        if not isinstance(raw, dict):
            raise TypeError("OAuth2 token response must be a JSON object")
        token_payload = cast(dict[str, Any], raw)
        access_token = token_payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise ValueError("OAuth2 token response must contain a non-empty string access_token")
        if "token_type" not in token_payload:
            warnings.warn(
                "OAuth2 token responses should include token_type; the implicit Bearer fallback "
                "is deprecated and will be removed no earlier than the next major apyra-auth "
                "release",
                DeprecationWarning,
                stacklevel=2,
                skip_file_prefixes=(str(Path(__file__).parent),),
            )
            token_type = "Bearer"
        else:
            token_type = token_payload["token_type"]
            if not isinstance(token_type, str) or not token_type:
                raise ValueError("OAuth2 token response must contain a non-empty string token_type")
        return OAuth2TokenResponse(
            access_token=access_token,
            token_type=token_type,
            expires_in=_optional_int(token_payload.get("expires_in")),
            refresh_token=_optional_str(token_payload.get("refresh_token")),
            id_token=_optional_str(token_payload.get("id_token")),
            scope=_optional_str(token_payload.get("scope")),
            raw=token_payload,
        )


class OIDCTokenValidator:
    """Validate OIDC ID tokens using Apyra's JWT authenticator."""

    def __init__(
        self,
        authenticator: Any,
        *,
        expected_nonce: str | None = None,
        expected_issuer: str | None = None,
        expected_audience: str | None = None,
    ) -> None:
        self._authenticator = authenticator
        self._expected_nonce = expected_nonce
        self._expected_issuer = expected_issuer
        self._expected_audience = expected_audience

    def validate(self, id_token: str) -> Any:
        """Verify an ID token and compare its configured issuer, audience, and nonce claims."""
        decoded = self._authenticator.decode_token(id_token)
        payload = decoded["payload"]
        if self._expected_issuer is not None and payload.get("iss") != self._expected_issuer:
            raise AuthenticationError("token_issuer_invalid")
        if self._expected_audience is not None:
            audience = payload.get("aud")
            if isinstance(audience, str):
                audiences = [audience]
            elif isinstance(audience, list) and all(
                isinstance(value, str) for value in cast(list[object], audience)
            ):
                audiences = cast(list[str], audience)
            else:
                raise AuthenticationError("token_audience_invalid")
            if self._expected_audience not in audiences:
                raise AuthenticationError("token_audience_invalid")
            authorized_party = payload.get("azp")
            if authorized_party is not None and authorized_party != self._expected_audience:
                raise AuthenticationError("token_authorized_party_invalid")
            if len(audiences) > 1 and authorized_party != self._expected_audience:
                raise AuthenticationError("token_authorized_party_invalid")
        if self._expected_nonce is not None and payload.get("nonce") != self._expected_nonce:
            raise ValueError("OIDC nonce mismatch")
        return decoded


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _https_endpoint(value: str, name: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise ValueError(f"{name} must use HTTPS and cannot contain user information")
    return value


class OIDCClient:
    """High-level OpenID Connect client combining discovery and OAuth2 flows."""

    scopes: list[str]

    def __init__(
        self,
        *,
        issuer: str,
        client_id: str,
        client_secret: str | None = None,
        authenticator: Any = None,
        redirect_uri: str | None = None,
        scopes: list[str] | None = None,
        discovery_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.issuer = issuer
        self.client_id = client_id
        self.client_secret = client_secret
        self.authenticator = authenticator
        self.redirect_uri = redirect_uri
        self.scopes = scopes or ["openid"]
        self.discovery_url = discovery_url
        self._transport = transport
        self._timeout = timeout_seconds
        self._configuration: OIDCConfiguration | None = None
        self._oauth2: OAuth2Client | None = None

    async def discover(self) -> OIDCConfiguration:
        """Load issuer metadata once and configure the OAuth2 client endpoints."""
        from .oidc import discover_oidc

        if self._configuration is None:
            self._configuration = await discover_oidc(
                self.issuer,
                discovery_url=self.discovery_url,
                transport=self._transport,
                timeout_seconds=self._timeout,
            )
            self._oauth2 = OAuth2Client(
                client_id=self.client_id,
                client_secret=self.client_secret,
                authorization_endpoint=self._configuration.authorization_endpoint or "",
                token_endpoint=self._configuration.token_endpoint or "",
                revocation_endpoint=self._configuration.revocation_endpoint,
                redirect_uri=self.redirect_uri,
                scopes=self.scopes,
                transport=self._transport,
                timeout_seconds=self._timeout,
            )
        return self._configuration

    async def _oauth2_client(self) -> OAuth2Client:
        if self._oauth2 is None:
            await self.discover()
        assert self._oauth2 is not None
        return self._oauth2

    async def authorization_url(
        self, *, state: str, nonce: str | None = None, code_challenge: str | None = None
    ) -> str:
        """Build an authorization URL with optional nonce and PKCE challenge."""
        await self.discover()
        extra = {"nonce": nonce} if nonce else None
        oauth2 = await self._oauth2_client()
        return oauth2.authorization_url(
            state=state, code_challenge=code_challenge, extra_params=extra
        )

    async def exchange_code(
        self, code: str, *, code_verifier: str | None = None, expected_nonce: str | None = None
    ) -> tuple[OAuth2TokenResponse, Any]:
        """Exchange a code and validate the returned ID token when configured."""
        oauth2 = await self._oauth2_client()
        token_response = await oauth2.exchange_code(code, code_verifier=code_verifier)
        decoded = None
        if token_response.id_token and self.authenticator is not None:
            validator = OIDCTokenValidator(
                self.authenticator,
                expected_nonce=expected_nonce,
                expected_issuer=self.issuer,
                expected_audience=self.client_id,
            )
            decoded = validator.validate(token_response.id_token)
        return token_response, decoded

    async def userinfo(self, access_token: str, *, expected_subject: str) -> dict[str, Any]:
        """Fetch user claims and bind the response to a verified ID Token subject."""
        if not expected_subject:
            raise ValueError("expected_subject must be a non-empty verified ID Token subject")
        config = await self.discover()
        if not config.userinfo_endpoint:
            raise ValueError("OIDC userinfo endpoint is not available")
        import httpx

        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.get(
                config.userinfo_endpoint, headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()
            data: object = response.json()
        if not isinstance(data, dict):
            raise TypeError("OIDC userinfo response must be a JSON object")
        userinfo = cast(dict[str, Any], data)
        subject = userinfo.get("sub")
        if not isinstance(subject, str) or subject != expected_subject:
            raise AuthenticationError("userinfo_subject_mismatch")
        return userinfo

    async def refresh_token(
        self, refresh_token: str, *, scope: str | None = None
    ) -> OAuth2TokenResponse:
        """Refresh tokens through the discovered OAuth2 token endpoint."""
        oauth2 = await self._oauth2_client()
        return await oauth2.refresh_token(refresh_token, scope=scope)

    async def revoke(self, token: str, *, token_type_hint: str | None = None) -> None:
        """Revoke a token through the discovered OAuth2 endpoint."""
        oauth2 = await self._oauth2_client()
        await oauth2.revoke(token, token_type_hint=token_type_hint)
