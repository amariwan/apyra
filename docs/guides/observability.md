# Observability

`apyra-observability` provides structured logging, error/performance monitoring primitives, and an
optional OpenTelemetry integration.

```bash
uv add 'apyra-observability[opentelemetry]'
```

```python
from apyra.observability import configure_logging, configure_opentelemetry

configure_logging(level="INFO", json_output=True)
configure_opentelemetry(service_name="orders-api")
```

Initialize telemetry once in the composition root and shut down providers/exporters during
application shutdown. Instrument HTTP, database, messaging, workflows, and tasks at their boundaries
so a trace follows the unit of work.

Do not attach request bodies, credentials, tokens, email addresses, or unrestricted tenant/user IDs
to spans and metrics. Prefer bounded route templates and operation names over raw paths or payload
values to avoid sensitive-data leakage and high-cardinality labels.

Exporter connectivity and dashboard provisioning are deployment concerns. A local successful span
creation does not verify delivery to a production collector.
