"""Framework-independent JWT authentication."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Protocol, TypedDict

import jwt

from .exceptions import AuthenticationError
from .keys import get_jwks_client
from .settings import AuthSettings, get_auth_settings

_HMAC_ALGORITHMS = frozenset({"HS256", "HS384", "HS512"})


class JWTHeader(TypedDict, total=False):
    """Recognized optional JOSE header fields returned by token decoding."""

    alg: str
    kid: str
    typ: str


class DecodedToken(TypedDict):
    """Verified JWT header and claims returned by an authenticator."""

    header: JWTHeader
    payload: dict[str, Any]


class JWTRevocationStore(Protocol):
    """Synchronous lookup contract used to reject revoked JWT identifiers."""

    def is_revoked(self, jti: str) -> bool:
        """Return whether the token identifier has been revoked."""
        ...

    def is_family_revoked(self, family_id: str) -> bool:
        """Return whether the refresh-token family has been revoked."""
        ...


class JWTAuthenticator:
    """Validate and decode JWTs without framework-specific exceptions."""

    def __init__(
        self,
        settings: AuthSettings | None = None,
        revocation_store: JWTRevocationStore | None = None,
    ) -> None:
        if revocation_store is not None and not all(
            callable(getattr(revocation_store, method, None))
            for method in ("is_revoked", "is_family_revoked")
        ):
            raise TypeError("revocation_store must implement is_revoked and is_family_revoked")
        self._settings = settings or get_auth_settings()
        self._revocation_store = revocation_store

    def decode_token(self, token: str) -> DecodedToken:
        """Verify a JWT's signature and claims, then enforce revocation checks."""
        self._validate_configuration()
        decoded, _ = self._decode_verified(token)
        self._check_revocation(decoded)
        return decoded

    def decode_access_token(self, token: str) -> DecodedToken:
        """Decode a JWT and enforce configured API access-token type markers."""
        self._validate_configuration()
        decoded, header_typ_present = self._decode_verified(token)
        self._check_revocation(decoded)
        expected_type = self._settings.expected_access_token_type
        if expected_type is not None and decoded["payload"].get("type") != expected_type:
            raise AuthenticationError("token_type_invalid")
        expected_header_typ = self._settings.expected_access_token_header_typ
        if expected_header_typ is not None and (
            not header_typ_present or decoded["header"].get("typ") != expected_header_typ
        ):
            raise AuthenticationError("token_header_type_invalid")
        return decoded

    def _check_revocation(self, decoded: DecodedToken) -> None:
        store = self._revocation_store
        if store is None:
            return
        payload = decoded["payload"]
        jti = payload.get("jti")
        if isinstance(jti, str) and store.is_revoked(jti):
            raise AuthenticationError("token_revoked")
        family = payload.get("family")
        if isinstance(family, str) and store.is_family_revoked(family):
            raise AuthenticationError("token_revoked")

    def _validate_configuration(self) -> None:
        if not self._settings.verify_signature:
            raise AuthenticationError("signature_verification_required")
        if not self._settings.verify_exp:
            raise AuthenticationError("expiration_verification_required")
        if self._settings.verify_iss and not self._settings.issuer:
            raise AuthenticationError("issuer_required")
        if self._settings.verify_aud and not self._settings.audience:
            raise AuthenticationError("audience_required")
        algorithms = _normalize_algorithms(self._settings.algorithms)
        if not algorithms:
            raise AuthenticationError("algorithms_required")
        if any(alg in {"", "NONE"} for alg in algorithms):
            raise AuthenticationError("algorithm_invalid")
        mode = self._settings.mode.lower()
        if mode == "jwks":
            if not self._settings.jwks_url:
                raise AuthenticationError("jwks_url_missing")
            if self._settings.jwks_url.scheme != "https":
                raise AuthenticationError("jwks_https_required")
            if (
                self._settings.jwks_url.username is not None
                or self._settings.jwks_url.password is not None
            ):
                raise AuthenticationError("jwks_url_userinfo_forbidden")
            if any(alg in _HMAC_ALGORITHMS for alg in algorithms):
                raise AuthenticationError("algorithm_invalid")
        elif mode == "hs":
            if self._settings.hs_secret is None:
                raise AuthenticationError("auth_hs_secret_missing")
            if any(alg not in _HMAC_ALGORITHMS for alg in algorithms):
                raise AuthenticationError("algorithm_invalid")
        else:
            raise AuthenticationError("auth_mode_invalid")

    def _decode_verified(self, token: str) -> tuple[DecodedToken, bool]:
        try:
            header_raw = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError("invalid_header") from exc
        if str(header_raw.get("alg", "")).upper() == "NONE":
            raise AuthenticationError("alg_none_forbidden")

        algorithms = _normalize_algorithms(self._settings.algorithms)
        mode = self._settings.mode.lower()

        options: dict[str, Any] = {
            "verify_signature": self._settings.verify_signature,
            "verify_exp": self._settings.verify_exp,
            "verify_nbf": True,
            "verify_iss": self._settings.verify_iss,
            "verify_aud": self._settings.verify_aud,
            "require": ["sub", "iat", "exp"],
        }
        kwargs: dict[str, Any] = {
            "algorithms": algorithms,
            "options": options,
            "leeway": self._settings.clock_skew_secs,
        }
        if self._settings.verify_iss and self._settings.issuer:
            kwargs["issuer"] = self._settings.issuer
        if self._settings.verify_aud and self._settings.audience:
            kwargs["audience"] = self._settings.audience

        payload = (
            self._decode_jwks(token, kwargs) if mode == "jwks" else self._decode_hs(token, kwargs)
        )

        header: JWTHeader = {
            "alg": str(header_raw.get("alg", "")),
            "kid": str(header_raw.get("kid", "")),
            "typ": str(header_raw.get("typ", "JWT")),
        }
        header_typ_present = isinstance(header_raw.get("typ"), str)
        return DecodedToken(header=header, payload=payload), header_typ_present

    def _decode_jwks(self, token: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        if not self._settings.jwks_url:
            raise AuthenticationError("jwks_url_missing")
        try:
            signing_key = get_jwks_client(str(self._settings.jwks_url)).get_signing_key_from_jwt(
                token
            )
        except (
            jwt.PyJWKClientError,
            jwt.PyJWKSetError,
            jwt.InvalidTokenError,
            RuntimeError,
        ) as exc:
            raise AuthenticationError("jwks_unavailable") from exc
        try:
            return jwt.decode(token, signing_key.key, **kwargs)
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError("token_expired") from exc
        except jwt.InvalidAudienceError as exc:
            raise AuthenticationError("token_audience_invalid") from exc
        except jwt.InvalidIssuerError as exc:
            raise AuthenticationError("token_issuer_invalid") from exc
        except jwt.InvalidSignatureError as exc:
            raise AuthenticationError("token_signature_invalid") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError("invalid_token") from exc

    def _decode_hs(self, token: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        if self._settings.hs_secret is None:
            raise AuthenticationError("auth_hs_secret_missing")
        secret = self._settings.hs_secret.get_secret_value()
        try:
            return jwt.decode(token, secret, **kwargs)
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError("token_expired") from exc
        except jwt.InvalidAudienceError as exc:
            raise AuthenticationError("token_audience_invalid") from exc
        except jwt.InvalidIssuerError as exc:
            raise AuthenticationError("token_issuer_invalid") from exc
        except jwt.InvalidSignatureError as exc:
            raise AuthenticationError("token_signature_invalid") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError("invalid_token") from exc


@lru_cache(maxsize=1)
def get_jwt_authenticator() -> JWTAuthenticator:
    """Return the cached authenticator built from current auth settings."""
    return JWTAuthenticator()


def reset_jwt_authenticator() -> None:
    """Clear the cached authenticator so later calls reload settings."""
    get_jwt_authenticator.cache_clear()


def _normalize_algorithms(algorithms: list[str] | str) -> list[str]:
    values = algorithms.split(",") if isinstance(algorithms, str) else algorithms
    return [str(algorithm).strip().upper() for algorithm in values]
