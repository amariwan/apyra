# apyra-observability

Logging, error, and performance monitoring primitives for Apyra.

## Purpose

`apyra-observability` provides structured logging, error reporting/capture, performance timing, and optional OpenTelemetry tracing/instrumentation. Core features have no required OpenTelemetry dependency.

## Installation

```bash
uv add apyra-observability                        # core
uv add "apyra-observability[opentelemetry]"       # + OTel SDK/exporters
```

## Minimal usage

```python
from apyra.observability import configure_logging, get_tracer

configure_logging()
tracer = get_tracer("my-service")
```

## Optional dependencies

- `opentelemetry`: `opentelemetry-api`, `opentelemetry-sdk`, OTLP exporter, FastAPI/SQLAlchemy instrumentation

## Configuration

Logging and telemetry helpers accept explicit arguments; OpenTelemetry is configured via `configure_opentelemetry`.

## Public API

- Logging: `configure_logging`, `get_request_id`, `set_request_id`, `setup_logging`
- Errors: `ErrorReporter`, `InMemoryErrorReporter`, `capture_exception`, `capture_message`, `monitor_errors`, `error_monitor`, `get_error_reporter`, `set_error_reporter`
- Performance: `PerformanceMonitor`, `PerformanceTimer`, `measure`, `record_duration`, `time_operation`, `get_performance_monitor`, `set_performance_monitor`
- Telemetry: `configure_opentelemetry`, `get_tracer`, `instrument_fastapi`, `instrument_sqlalchemy`, `span`

## Error behavior

Monitoring failures are captured, not raised, to avoid masking application errors. Configuration errors raise normally.

## Integration

`apyra-fastapi` integrates monitoring middleware. Combine with `apyra-db` for SQLAlchemy instrumentation.

## Compatibility

- Python ≥ 3.12
- OpenTelemetry extras require ≥ 1.25

## License

MIT
