# apyra-ai

AI client primitives for Apyra.

## Purpose

`apyra-ai` provides an OpenAI-compatible AI client (`AIClient`) built on httpx and Pydantic. It is provider-agnostic and targets OpenAI-style chat/completion endpoints.

## Installation

```bash
uv add apyra-ai
```

## Minimal usage

```python
from apyra.ai import AIClient

client = AIClient(base_url="https://api.openai.com/v1", api_key="...")
```

## Optional dependencies

- `openai`: reserved extra (currently empty).

## Configuration

Configure via constructor arguments (base URL, API key, model). No global settings object.

## Public API

- `AIClient`

## Error behavior

HTTP and validation errors propagate from httpx/Pydantic. No silent retries.

## Integration

Use within application services/use cases. Combine with `apyra-fastapi` to expose AI endpoints.

## Compatibility

- Python ≥ 3.12
- httpx ≥ 0.27, pydantic ≥ 2.8

## License

MIT
