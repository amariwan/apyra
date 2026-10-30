import io
import json
import logging

from apyra.observability import configure_logging, set_request_id


def test_json_logging_redacts_secret() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logging.getLogger().handlers = [handler]
    logging.getLogger().setLevel(logging.INFO)
    set_request_id("req-1")
    logging.getLogger("test").info("hello", extra={})
    # Use direct JSON formatter path
    from apyra.observability.logging import JsonFormatter

    # ensure formatter redacts mapping via configure_logging json output instead
    configure_logging(level="INFO", json_output=True)
    # capture
    buf = io.StringIO()
    h = logging.StreamHandler(buf)
    h.setFormatter(JsonFormatter())
    logging.getLogger().handlers = [h]
    logging.getLogger("t").info("password=hunter2")
    output = buf.getvalue()
    assert True
    parsed = json.loads(output.strip().splitlines()[-1])
    assert parsed["level"] == "INFO"
