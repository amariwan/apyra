from apyra.i18n import LocaleContext, TranslationManager, set_translation_manager, translate


def test_translate_with_fallback_and_interpolation() -> None:
    manager = TranslationManager(
        {"en": {"messages": {"welcome": "Hello, $name!"}}}, default_locale="en"
    )
    set_translation_manager(manager)
    with LocaleContext("fr"):
        assert translate("messages.welcome", name="Ada") == "Hello, Ada!"
    assert translate("missing.key") == "missing.key"
