from pathlib import Path

import pytest

from apyra.i18n import (
    LocaleContext,
    TranslationManager,
    set_translation_manager,
    translate,
    translate_validation_errors,
)


def test_translation_manager_rejects_non_object_catalogs(tmp_path: Path) -> None:
    catalog_file = tmp_path / "en.json"
    catalog_file.write_text('["not", "a", "catalog"]', encoding="utf-8")

    with pytest.raises(ValueError, match="JSON object"):
        TranslationManager.from_directory(tmp_path)


def test_translate_with_fallback_and_interpolation() -> None:
    manager = TranslationManager(
        {"en": {"messages": {"welcome": "Hello, $name!"}}}, default_locale="en"
    )
    set_translation_manager(manager)
    with LocaleContext("fr"):
        assert translate("messages.welcome", name="Ada") == "Hello, Ada!"
    assert translate("missing.key") == "missing.key"


def test_translation_manager_uses_its_default_locale_without_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = TranslationManager(
        {
            "de": {"greeting": "Hallo"},
            "en": {"greeting": "Hello"},
        },
        default_locale="de",
        fallback_locale="en",
    )
    monkeypatch.setattr("apyra.i18n.translation._manager", manager)

    assert translate("greeting") == "Hallo"

    with LocaleContext("en"):
        assert translate("greeting") == "Hello"


def test_translate_validation_errors_preserves_details_and_uses_locale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = TranslationManager(
        {"fr": {"validation": {"string_type": "Le champ doit être du texte."}}}
    )
    monkeypatch.setattr("apyra.i18n.translation._manager", manager)
    error = {"type": "string_type", "msg": "Input should be a valid string", "loc": ("name",)}

    translated = translate_validation_errors([error], locale="fr")

    assert translated == [
        {"type": "string_type", "msg": "Le champ doit être du texte.", "loc": ("name",)}
    ]
    assert error["msg"] == "Input should be a valid string"


def test_translate_validation_errors_falls_back_for_unknown_or_missing_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "apyra.i18n.translation._manager",
        TranslationManager({"en": {"validation": {"known": "Translated"}}}),
    )
    errors = (
        error
        for error in (
            {"type": "unknown", "msg": "Original unknown"},
            {"msg": "Original without type"},
        )
    )

    assert translate_validation_errors(errors) == [
        {"type": "unknown", "msg": "Original unknown"},
        {"msg": "Original without type"},
    ]
