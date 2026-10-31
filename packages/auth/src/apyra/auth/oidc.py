"""OIDC discovery and OAuth2 introspection helpers."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urljoin, urlsplit

if TYPE_CHECKING:
    import httpx


@dataclass(frozen=True, slots=True)
class OIDCConfiguration:
    """Validated issuer metadata and its supported HTTPS endpoints."""

    issuer: str
    authorization_endpoint: str | None
    token_endpoint: str | None
    userinfo_endpoint: str | None
    revocation_endpoint: str | None
    jwks_uri: str
    scopes_supported: tuple[str, ...]


async def discover_oidc(
    issuer: str,
    *,
    discovery_url: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    timeout_seconds: float = 10.0,
) -> OIDCConfiguration:
    """Fetch and validate an OpenID Connect discovery document."""

    base = issuer.rstrip("/") + "/"
    url = discovery_url or urljoin(base, ".well-known/openid-configuration")
    _require_https(issuer, "issuer")
    _require_https(url, "discovery_url")
    import httpx

    async with httpx.AsyncClient(timeout=timeout_seconds, transport=transport) as client:
        response = await client.get(url)
        response.raise_for_status()
        data: object = response.json()

    if not isinstance(data, dict):
        raise TypeError("OIDC discovery document must be a JSON object")
    metadata = cast(dict[str, Any], data)

    discovered_issuer = metadata.get("issuer")
    if discovered_issuer != issuer:
        raise ValueError("OIDC issuer mismatch")
    jwks_uri = metadata.get("jwks_uri")
    if not isinstance(jwks_uri, str) or not jwks_uri:
        raise ValueError("OIDC jwks_uri is required")
    endpoints = {
        "jwks_uri": jwks_uri,
        "authorization_endpoint": metadata.get("authorization_endpoint"),
        "token_endpoint": metadata.get("token_endpoint"),
        "userinfo_endpoint": metadata.get("userinfo_endpoint"),
        "revocation_endpoint": metadata.get("revocation_endpoint"),
    }
    for name, endpoint in endpoints.items():
        if endpoint is not None:
            if not isinstance(endpoint, str):
                raise ValueError(f"OIDC {name} must be a URL")
            _require_https(endpoint, name)
    scopes: object = metadata.get("scopes_supported") or []
    if not isinstance(scopes, list):
        scopes = []
    supported_scopes = cast(list[object], scopes)
    return OIDCConfiguration(
        issuer=str(discovered_issuer),
        authorization_endpoint=_optional_str(metadata.get("authorization_endpoint")),
        token_endpoint=_optional_str(metadata.get("token_endpoint")),
        userinfo_endpoint=_optional_str(metadata.get("userinfo_endpoint")),
        revocation_endpoint=_optional_str(metadata.get("revocation_endpoint")),
        jwks_uri=jwks_uri,
        scopes_supported=tuple(str(scope) for scope in supported_scopes),
    )


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _require_https(url: str, name: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError(f"OIDC {name} must use HTTPS and cannot contain user information")


class OAuth2TokenIntrospector:
    """RFC 7662 token introspection client."""

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        introspection_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        _require_https(introspection_url, "introspection_url")
        self._introspection_url = introspection_url
        self._transport = transport
        self._timeout = timeout_seconds

    async def introspect(self, token: str) -> dict[str, Any]:
        """Send an RFC 7662 introspection request using client credentials."""
        credentials = base64.b64encode(f"{self._client_id}:{self._client_secret}".encode()).decode(
            "ascii"
        )
        import httpx

        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.post(
                self._introspection_url,
                headers={"Authorization": f"Basic {credentials}"},
                data={"token": token},
            )
            response.raise_for_status()
            data: object = response.json()
        if not isinstance(data, dict):
            raise TypeError("OAuth2 introspection response must be a JSON object")
        return cast(dict[str, Any], data)
