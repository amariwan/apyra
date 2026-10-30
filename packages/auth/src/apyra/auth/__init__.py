"""Authentication and authorization for Apyra."""

from __future__ import annotations

from .exceptions import AuthenticationError, AuthorizationError
from .jwt import DecodedToken, JWTAuthenticator, get_jwt_authenticator, reset_jwt_authenticator
from .keys import get_jwks_client, reset_jwks_client
from .policy import (
    AllOfPolicy,
    AnyOfPolicy,
    AttributePolicy,
    InMemorySessionStore,
    Policy,
    PolicyEngine,
    RolePolicy,
    ScopePolicy,
    Session,
    SessionStore,
)

JWTAuthService = JWTAuthenticator
get_jwt_service = get_jwt_authenticator
reset_jwt_service = reset_jwt_authenticator
from .oauth2 import (
    OAuth2Client,
    OAuth2TokenResponse,
    OIDCClient,
    OIDCTokenValidator,
    generate_pkce_pair,
)
from .oidc import OAuth2TokenIntrospector, OIDCConfiguration, discover_oidc
from .roles import extract_roles, extract_scopes, has_role
from .settings import AuthSettings, get_auth_settings
from .tokens import (
    InMemoryRevocationStore,
    InMemoryTokenBlocklist,
    TokenIssuer,
    TokenPair,
    TokenService,
)

__all__ = [
    "AllOfPolicy",
    "AnyOfPolicy",
    "AttributePolicy",
    "AuthSettings",
    "AuthenticationError",
    "AuthorizationError",
    "DecodedToken",
    "InMemoryRevocationStore",
    "InMemorySessionStore",
    "InMemoryTokenBlocklist",
    "JWTAuthService",
    "JWTAuthenticator",
    "OAuth2Client",
    "OAuth2TokenIntrospector",
    "OAuth2TokenResponse",
    "OIDCClient",
    "OIDCConfiguration",
    "OIDCTokenValidator",
    "Policy",
    "PolicyEngine",
    "RolePolicy",
    "ScopePolicy",
    "Session",
    "SessionStore",
    "TokenIssuer",
    "TokenPair",
    "TokenService",
    "discover_oidc",
    "extract_roles",
    "extract_scopes",
    "generate_pkce_pair",
    "get_auth_settings",
    "get_jwks_client",
    "get_jwt_authenticator",
    "get_jwt_service",
    "has_role",
    "reset_jwks_client",
    "reset_jwt_authenticator",
    "reset_jwt_service",
]
