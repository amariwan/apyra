# apyra-ai

OpenAI-compatible AI client for Apyra.

## Installation

```bash
uv add apyra-ai
```

## Quick usage

```python
from apyra.ai import AIClient

client = AIClient(api_key="sk-...", base_url="https://api.openai.com/v1")
```

The client requires HTTPS for remote endpoints. Plain HTTP is allowed for loopback development endpoints; set `allow_insecure_http=True` only when a trusted private deployment requires HTTP. HTTP does not protect prompts or API keys in transit.

## License

MIT
