# apyra-i18n

Internationalization primitives for Apyra.

## Purpose

`apyra-i18n` provides locale context management, a translation manager, and validation error translation. Framework-independent.

## Installation

```bash
uv add apyra-i18n
```

## Minimal usage

```python
from apyra.i18n import set_locale, translate

set_locale("fr")
text = translate("greeting")
```

## Optional dependencies

None.

## Configuration

Translation manager is configured explicitly via `set_translation_manager`.

## Public API

- `LocaleContext`, `get_locale`, `set_locale`
- `TranslationManager`, `set_translation_manager`, `translate`
- `translate_validation_errors`

## Error behavior

Missing translations fall back according to the configured manager; invalid locale raises standard errors.

## Integration

Combine with `apyra-fastapi` to localize responses and validation errors.

## Compatibility

- Python ≥ 3.12
- Depends on `apyra-core>=0.1.0,<0.2.0`

## License

MIT
