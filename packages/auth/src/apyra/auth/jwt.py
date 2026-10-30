"""Framework-independent JWT authentication."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, TypedDict

import jwt

from .exceptions import AuthenticationError
from .keys import get_jwks_client
from .settings import AuthSettings, get_auth_settings

_HMAC_ALGORITHMS = frozenset({"HS256", "HS384", "HS512"})


class JWTHeader(TypedDict, total=False):
    alg: str
    kid: str
    typ: str


class DecodedToken(TypedDict):
    header: JWTHeader
    payload: dict[str, Any]


class JWTAuthenticator:
    """Validate and decode JWTs without framework-specific exceptions."""

    def __init__(self, settings: AuthSettings | None = None, revocation_store: Any = None) -> None:
        self._settings = settings or get_auth_settings()
        self._revocation_store = revocation_store

    def decode_token(self, token: str) -> DecodedToken:
        self._validate_configuration()
        decoded = self._decode_verified(token)
        self._check_revocation(decoded)
        return decoded

    def _check_revocation(self, decoded: DecodedToken) -> None:
        store = self._revocation_store
        if store is None:
            return
        payload = decoded["payload"]
        jti = payload.get("jti")
        if isinstance(jti, str) and getattr(store, "is_revoked", lambda _value: False)(jti):
            raise AuthenticationError("token_revoked")
        family = payload.get("family")
        if isinstance(family, str) and getattr(store, "is_family_revoked", lambda _value: False)(
            family
        ):
            raise AuthenticationError("token_revoked")

    def _validate_configuration(self) -> None:
        if not self._settings.verify_signature:
            raise AuthenticationError("signature_verification_required")
        if not self._settings.algorithms:
            raise AuthenticationError("algorithms_required")
        algorithms = [str(alg).upper() for alg in self._settings.algorithms]
        if any(alg in {"", "NONE"} for alg in algorithms):
            raise AuthenticationError("algorithm_invalid")
        mode = self._settings.mode.lower()
        if mode == "jwks":
            if not self._settings.jwks_url:
                raise AuthenticationError("jwks_url_missing")
            if any(alg in _HMAC_ALGORITHMS for alg in algorithms):
                raise AuthenticationError("algorithm_invalid")
        elif mode == "hs":
            if self._settings.hs_secret is None:
                raise AuthenticationError("auth_hs_secret_missing")
            if not any(alg in _HMAC_ALGORITHMS for alg in algorithms):
                raise AuthenticationError("algorithm_invalid")
        else:
            raise AuthenticationError("auth_mode_invalid")

    def _decode_verified(self, token: str) -> DecodedToken:
        try:
            header_raw = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError("invalid_header") from exc
        if str(header_raw.get("alg", "")).upper() == "NONE":
            raise AuthenticationError("alg_none_forbidden")

        algorithms = [alg.upper() for alg in self._settings.algorithms] or ["RS256"]
        mode = self._settings.mode.lower()
        if mode == "jwks":
            algorithms = [alg for alg in algorithms if alg not in _HMAC_ALGORITHMS] or ["RS256"]
        elif mode == "hs" and not any(alg in _HMAC_ALGORITHMS for alg in algorithms):
            algorithms.append("HS256")

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

        if mode == "jwks":
            payload = self._decode_jwks(token, kwargs)
        elif mode == "hs":
            payload = self._decode_hs(token, kwargs)
        else:
            raise AuthenticationError("auth_mode_invalid")

        header: JWTHeader = {
            "alg": str(header_raw.get("alg", "")),
            "kid": str(header_raw.get("kid", "")),
            "typ": str(header_raw.get("typ", "JWT")),
        }
        return DecodedToken(header=header, payload=payload)

    def _decode_jwks(self, token: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        if not self._settings.jwks_url:
            raise AuthenticationError("jwks_url_missing")
        try:
            signing_key = get_jwks_client().get_signing_key_from_jwt(token)
        except (jwt.PyJWKClientConnectionError, jwt.PyJWKSetError, RuntimeError) as exc:
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
    return JWTAuthenticator()


def reset_jwt_authenticator() -> None:
    get_jwt_authenticator.cache_clear()
