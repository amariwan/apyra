from apyra.security import (
    constant_time_compare,
    generate_api_key,
    generate_csrf_token,
    hash_password,
    redact_mapping,
    verify_api_key,
    verify_csrf_token,
    verify_password,
)


def test_password_round_trip() -> None:
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong", hashed)


def test_api_key_round_trip() -> None:
    key, hashed = generate_api_key()
    assert verify_api_key(key, hashed)
    assert not verify_api_key(key + "x", hashed)


def test_csrf_round_trip() -> None:
    token = generate_csrf_token("secret")
    assert verify_csrf_token(token, "secret")
    assert not verify_csrf_token(token, "other")


def test_constant_time_compare() -> None:
    assert constant_time_compare("abc", "abc")
    assert not constant_time_compare("abc", "def")


def test_redact_mapping() -> None:
    assert redact_mapping({"password": "secret", "nested": {"token": "x"}, "safe": 1}) == {
        "password": "***REDACTED***",
        "nested": {"token": "***REDACTED***"},
        "safe": 1,
    }
