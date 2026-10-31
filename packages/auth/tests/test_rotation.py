import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, tzinfo
from threading import Barrier

import jwt
import pytest
from pydantic import SecretStr

from apyra.auth import (
    AuthenticationError,
    AuthSettings,
    InMemoryRevocationStore,
    TokenPair,
    TokenService,
)


def _settings() -> AuthSettings:
    return AuthSettings(
        mode="hs",
        hs_secret=SecretStr("secret-with-enough-length-for-hs256"),
        algorithms=["HS256"],
        issuer="apyra-tests",
        audience="apyra-api",
    )


def test_refresh_rotation_revokes_old_token() -> None:
    service = TokenService(_settings())
    pair = service.issue_token_pair("user-1", scopes=["read"])
    rotated = service.refresh(pair.refresh_token)
    assert rotated.access_token != pair.access_token
    old = jwt.decode(
        pair.refresh_token,
        "secret-with-enough-length-for-hs256",
        algorithms=["HS256"],
        issuer="apyra-tests",
        audience="apyra-api",
    )
    assert service.store.is_revoked(str(old["jti"]))


@pytest.mark.parametrize("scopes", ["admin", ["read", 7]])
def test_refresh_rejects_malformed_scope_claim(scopes: str | list[str | int]) -> None:
    service = TokenService(_settings())
    now = int(time.time())
    malformed_token = jwt.encode(
        {
            "sub": "user-1",
            "type": "refresh",
            "iat": now,
            "exp": now + 3600,
            "jti": "malformed-scopes",
            "family": "family-1",
            "scopes": scopes,
            "iss": "apyra-tests",
            "aud": "apyra-api",
        },
        "secret-with-enough-length-for-hs256",
        algorithm="HS256",
    )

    with pytest.raises(AuthenticationError, match="invalid_token"):
        service.refresh(malformed_token)


def test_refresh_accepts_legacy_token_without_scope_claim() -> None:
    service = TokenService(_settings())
    now = int(time.time())
    legacy_token = jwt.encode(
        {
            "sub": "user-1",
            "type": "refresh",
            "iat": now,
            "exp": now + 3600,
            "jti": "legacy-refresh",
            "family": "family-1",
            "iss": "apyra-tests",
            "aud": "apyra-api",
        },
        "secret-with-enough-length-for-hs256",
        algorithm="HS256",
    )

    rotated = service.refresh(legacy_token)

    assert service.verify_access_token(rotated.access_token)["scopes"] == []


def test_refresh_reuse_revokes_family() -> None:
    service = TokenService(_settings())
    pair = service.issue_token_pair("user-1")
    service.refresh(pair.refresh_token)
    with pytest.raises(AuthenticationError, match="token_reuse_detected"):
        service.refresh(pair.refresh_token)
    decoded = jwt.decode(
        pair.refresh_token,
        "secret-with-enough-length-for-hs256",
        algorithms=["HS256"],
        issuer="apyra-tests",
        audience="apyra-api",
    )
    assert service.store.is_family_revoked(str(decoded["family"]))


def test_refresh_reuse_revokes_access_tokens_in_family() -> None:
    service = TokenService(_settings())
    pair = service.issue_token_pair("user-1")
    service.refresh(pair.refresh_token)

    with pytest.raises(AuthenticationError, match="token_reuse_detected"):
        service.refresh(pair.refresh_token)

    with pytest.raises(AuthenticationError, match="token_revoked"):
        service.verify_access_token(pair.access_token)


def test_refresh_reuse_revokes_rotated_access_through_its_expiration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ControlledDateTime(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> datetime:
            return datetime.fromtimestamp(current_time[0], tz=tz)

    current_time = [int(time.time())]
    initial_time = current_time[0]
    monkeypatch.setattr("apyra.auth.tokens.time.time", lambda: current_time[0])
    monkeypatch.setattr("jwt.api_jwt.datetime", ControlledDateTime)
    service = TokenService(_settings())
    pair = service.issue_token_pair("user-1")

    current_time[0] = initial_time + 3599
    rotated = service.refresh(pair.refresh_token)
    with pytest.raises(AuthenticationError, match="token_reuse_detected"):
        service.refresh(pair.refresh_token)

    current_time[0] = initial_time + 3601
    with pytest.raises(AuthenticationError, match="token_revoked"):
        service.verify_access_token(rotated.access_token)


def test_revoke_refresh_keeps_family_revoked_through_access_expiration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_time = [int(time.time())]
    monkeypatch.setattr("apyra.auth.tokens.time.time", lambda: current_time[0])
    service = TokenService(_settings())
    pair = service.issue_token_pair("user-1", access_expires_in=7200, refresh_expires_in=3600)

    service.revoke(pair.refresh_token)
    current_time[0] += 3601

    with pytest.raises(AuthenticationError, match="token_revoked"):
        service.verify_access_token(pair.access_token)


def test_legacy_revocation_store_remains_compatible() -> None:
    class LegacyStore:
        def __init__(self) -> None:
            self.revoked: set[str] = set()
            self.families: set[str] = set()

        def revoke(self, jti: str, expires_at: float | None = None) -> None:
            self.revoked.add(jti)

        def revoke_family(self, family_id: str) -> None:
            self.families.add(family_id)

        def is_revoked(self, jti: str) -> bool:
            return jti in self.revoked

        def is_family_revoked(self, family_id: str) -> bool:
            return family_id in self.families

    store = LegacyStore()
    service = TokenService(_settings(), store=store)
    pair = service.issue_token_pair("user-1")

    service.refresh(pair.refresh_token)
    with pytest.raises(AuthenticationError, match="token_reuse_detected"):
        service.refresh(pair.refresh_token)

    assert store.families


def test_revoke_access_token() -> None:
    service = TokenService(_settings())
    pair = service.issue_token_pair("user-1")
    service.revoke(pair.access_token)
    with pytest.raises(AuthenticationError, match="token_revoked"):
        service.verify_access_token(pair.access_token)


def test_concurrent_refresh_reuse_only_issues_one_pair_and_revokes_family() -> None:
    class RacingStore(InMemoryRevocationStore):
        def __init__(self) -> None:
            super().__init__()
            self.both_checked = Barrier(2)
            self.force_race = True

        def consume_refresh_token_until(self, jti: str, family_id: str, expires_at: float) -> bool:
            if self.force_race:
                self.both_checked.wait(timeout=2)
            return super().consume_refresh_token_until(jti, family_id, expires_at)

    store = RacingStore()
    service = TokenService(_settings(), store=store)
    pair = service.issue_token_pair("user-1")

    def rotate() -> TokenPair | AuthenticationError:
        try:
            return service.refresh(pair.refresh_token)
        except AuthenticationError as exc:
            return exc

    def rotate_for_worker(_index: int) -> TokenPair | AuthenticationError:
        return rotate()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(rotate_for_worker, range(2)))

    store.force_race = False
    issued = [result for result in results if isinstance(result, TokenPair)]
    rejected = [result for result in results if isinstance(result, AuthenticationError)]
    assert len(issued) == 1
    assert len(rejected) == 1
    with pytest.raises(AuthenticationError, match="token_revoked"):
        service.verify_access_token(issued[0].access_token)


def test_in_memory_revocations_expire_with_token_lifetime(monkeypatch: pytest.MonkeyPatch) -> None:
    current_time = [100.0]
    monkeypatch.setattr("apyra.auth.tokens.time.time", lambda: current_time[0])
    store = InMemoryRevocationStore()
    expires_at = current_time[0] + 1

    assert store.consume_refresh_token_until("refresh-jti", "family-1", expires_at)
    assert not store.consume_refresh_token_until("refresh-jti", "family-1", expires_at)
    assert store.is_revoked("refresh-jti")
    assert store.is_family_revoked("family-1")

    current_time[0] = expires_at + 1

    assert not store.is_revoked("refresh-jti")
    assert not store.is_family_revoked("family-1")
