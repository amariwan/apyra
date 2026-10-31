import base64
import hashlib

import pytest

from apyra.security import (
    constant_time_compare,
    generate_api_key,
    generate_csrf_token,
    hash_password,
    password_hash_needs_rehash,
    redact_mapping,
    verify_api_key,
    verify_csrf_token,
    verify_password,
)


def test_password_round_trip() -> None:
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong", hashed)


def test_password_hash_records_its_pbkdf2_work_factor() -> None:
    hashed = hash_password("correct horse battery staple")

    assert hashed.split("$", 2)[:2] == ["pbkdf2_sha256", "600000"]


def test_password_verification_keeps_accepting_legacy_hashes() -> None:
    password = "legacy password"
    salt = b"0123456789abcdef"
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 390_000)
    stored_hash = (
        f"pbkdf2_sha256${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"
    )

    assert verify_password(password, stored_hash)
    assert not verify_password("wrong password", stored_hash)


def test_password_hash_rehash_indicator_supports_legacy_migration() -> None:
    password = "legacy password"
    salt = b"0123456789abcdef"
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 390_000)
    legacy_hash = (
        f"pbkdf2_sha256${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"
    )

    assert not password_hash_needs_rehash(hash_password(password))
    assert password_hash_needs_rehash(legacy_hash)
    assert password_hash_needs_rehash("malformed hash")


@pytest.mark.parametrize(
    "iterations", ["389999", "2000001", "not-a-number", "６０００００", "9" * 5000]
)
def test_password_verification_rejects_unsupported_work_factors(iterations: str) -> None:
    salt = base64.b64encode(b"0123456789abcdef").decode()
    digest = base64.b64encode(b"d" * hashlib.sha256().digest_size).decode()

    assert not verify_password("password", f"pbkdf2_sha256${iterations}${salt}${digest}")


@pytest.mark.parametrize(
    "stored_hash",
    [
        "not-a-hash",
        "pbkdf2_sha256$é$YWJj",
        "pbkdf2_sha256$%%%$%%%",
        "pbkdf2_sha256$YQ==$YQ==",
        "pbkdf2_sha256$"
        + base64.b64encode(b"s" * 16).decode("ascii")
        + "$"
        + base64.b64encode(b"d" * 31).decode("ascii"),
    ],
)
def test_password_verification_rejects_malformed_hashes(stored_hash: str) -> None:
    assert not verify_password("password", stored_hash)


def test_api_key_round_trip() -> None:
    key, hashed = generate_api_key()
    assert verify_api_key(key, hashed)
    assert not verify_api_key(key + "x", hashed)


@pytest.mark.parametrize("stored_hash", ["é" * 64, "a" * 63, "g" * 64, "a" * 65])
def test_api_key_verification_rejects_malformed_hashes(stored_hash: str) -> None:
    assert not verify_api_key("some-key", stored_hash)


def test_csrf_round_trip() -> None:
    secret = "csrf-test-secret-with-at-least-32-bytes"
    token = generate_csrf_token(secret)
    assert verify_csrf_token(token, secret)
    assert not verify_csrf_token(token, "another-csrf-test-secret-with-32-bytes")
    assert not verify_csrf_token("nonce.ø", secret)


def test_csrf_tokens_reject_short_secrets() -> None:
    short_secret = "s" * 31

    with pytest.raises(ValueError, match="at least 32 bytes"):
        generate_csrf_token(short_secret)

    assert not verify_csrf_token("nonce.signature", short_secret)


def test_csrf_token_can_be_bound_to_a_session() -> None:
    secret = "csrf-test-secret-with-at-least-32-bytes"
    token = generate_csrf_token(secret, binding="session-123")

    assert verify_csrf_token(token, secret, binding="session-123")
    assert not verify_csrf_token(token, secret, binding="session-456")
    assert not verify_csrf_token(token, secret)


def test_csrf_binding_encoding_is_unambiguous() -> None:
    secret = "csrf-test-secret-with-at-least-32-bytes"
    token = generate_csrf_token(secret, binding="session\x00owner")
    nonce, signature = token.split(".", 1)
    ambiguous_token = f"owner\x00{nonce}.{signature}"

    assert not verify_csrf_token(ambiguous_token, secret, binding="session")


def test_constant_time_compare() -> None:
    assert constant_time_compare("abc", "abc")
    assert not constant_time_compare("abc", "def")


def test_redact_mapping() -> None:
    assert redact_mapping({"password": "secret", "nested": {"token": "x"}, "safe": 1}) == {
        "password": "***REDACTED***",
        "nested": {"token": "***REDACTED***"},
        "safe": 1,
    }


def test_redact_mapping_masks_cookie_credentials() -> None:
    assert redact_mapping(
        {"Cookie": "session=secret", "nested": {"set-cookie": "session=secret; HttpOnly"}}
    ) == {
        "Cookie": "***REDACTED***",
        "nested": {"set-cookie": "***REDACTED***"},
    }


def test_redact_mapping_masks_secrets_in_nested_sequences() -> None:
    assert redact_mapping({"items": [[{"access-token": "secret"}]]}) == {
        "items": [[{"access-token": "***REDACTED***"}]]
    }
    assert redact_mapping({"items": ({"api-key": "secret"},)}) == {
        "items": ({"api-key": "***REDACTED***"},)
    }
