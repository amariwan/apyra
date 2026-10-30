from apyra.core import Settings


def test_settings_defaults_are_safe() -> None:
    settings = Settings()

    assert settings.app_name == "Apyra"
    assert settings.debug is False
    assert settings.normalized_api_prefix() == ""


def test_settings_normalize_api_prefix() -> None:
    settings = Settings(api_prefix="api/v1/")

    assert settings.normalized_api_prefix() == "/api/v1"
