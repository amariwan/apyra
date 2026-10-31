import io
import json
import logging
import sys

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
    assert "hunter2" not in output
    assert "***REDACTED***" in output
    parsed = json.loads(output.strip().splitlines()[-1])
    assert parsed["level"] == "INFO"


def test_json_logging_redacts_authorization_values_in_message_and_exception() -> None:
    from apyra.observability.logging import JsonFormatter

    formatter = JsonFormatter()
    message_secret = "message-bearer-secret"
    message = formatter.format(
        logging.makeLogRecord(
            {
                "msg": "Authorization: Bearer %s; trace=message-context",
                "args": (message_secret,),
                "levelname": "INFO",
                "name": "test",
            }
        )
    )
    json_message = formatter.format(
        logging.makeLogRecord(
            {
                "msg": '{"Authorization": "Bearer quoted-bearer-secret"}',
                "levelname": "INFO",
                "name": "test",
            }
        )
    )

    try:
        raise ValueError("Authorization: Bearer exception-bearer-secret; trace=exception-context")
    except ValueError:
        exception = formatter.format(
            logging.makeLogRecord(
                {
                    "msg": "request failed",
                    "levelname": "ERROR",
                    "name": "test",
                    "exc_info": sys.exc_info(),
                }
            )
        )

    parsed_message = json.loads(message)
    parsed_json_message = json.loads(json_message)
    parsed_exception = json.loads(exception)
    assert message_secret not in message
    assert parsed_message["message"] == "Authorization: ***REDACTED***; trace=message-context"
    assert "quoted-bearer-secret" not in json_message
    assert parsed_json_message["message"] == '{"Authorization": "***REDACTED***"}'
    assert "exception-bearer-secret" not in exception
    assert "***REDACTED***" in parsed_exception["exception"]
    assert "trace=exception-context" in parsed_exception["exception"]


def test_json_logging_redacts_cookie_headers_in_message_and_json_text() -> None:
    from apyra.observability.logging import JsonFormatter

    formatter = JsonFormatter()
    messages = [
        "Cookie: session=cookie-header-secret; refresh=refresh-header-secret\nhandler=auth-context",
        "Set-Cookie: session=set-cookie-secret; HttpOnly; SameSite=Lax",
        '{"Cookie": "session=json-cookie-secret; refresh=json-refresh-secret"}',
    ]
    outputs = [
        formatter.format(
            logging.makeLogRecord({"msg": message, "levelname": "INFO", "name": "test"})
        )
        for message in messages
    ]
    parsed = [json.loads(output)["message"] for output in outputs]

    assert all(
        secret not in "".join(outputs)
        for secret in (
            "cookie-header-secret",
            "refresh-header-secret",
            "set-cookie-secret",
            "json-cookie-secret",
            "json-refresh-secret",
        )
    )
    assert parsed[0] == (
        "Cookie: session=***REDACTED***; refresh=***REDACTED***\nhandler=auth-context"
    )
    assert parsed[1] == "Set-Cookie: session=***REDACTED***; HttpOnly; SameSite=Lax"
    assert parsed[2] == '{"Cookie": "session=***REDACTED***; refresh=***REDACTED***"}'

    mapping_output = formatter.format(
        logging.makeLogRecord(
            {
                "msg": "payload=%s",
                "args": ({"Set-Cookie": "session=python-set-cookie-secret"},),
                "levelname": "INFO",
                "name": "test",
            }
        )
    )
    assert "python-set-cookie-secret" not in mapping_output
    assert json.loads(mapping_output)["message"] == ("payload={'Set-Cookie': '***REDACTED***'}")

    for header_value in (
        "{'Set-Cookie': ['session=list-secret']}",
        "{'Cookie': ('session=tuple-secret', 'refresh=tuple-refresh-secret')}",
        "{'Set-Cookie': {'session': 'nested-dict-secret'}}",
        "{'Set-Cookie': b'session=bytes-cookie-secret'}",
        "{'Set-Cookie': bytearray(b'session=bytearray-cookie-secret')}",
        "[(b'cookie', b'session=raw-header-secret')]",
        repr({"Set-Cookie": b"session=prefix')tail-bytes-secret"}),
        repr({"Set-Cookie": bytearray(b"session=prefix')tail-bytearray-secret")}),
    ):
        output = formatter.format(
            logging.makeLogRecord(
                {"msg": "payload=%s", "args": (header_value,), "levelname": "INFO", "name": "test"}
            )
        )
        assert "list-secret" not in output
        assert "tuple-secret" not in output
        assert "tuple-refresh-secret" not in output
        assert "nested-dict-secret" not in output
        assert "bytes-cookie-secret" not in output
        assert "bytearray-cookie-secret" not in output
        assert "raw-header-secret" not in output
        assert "tail-bytes-secret" not in output
        assert "tail-bytearray-secret" not in output


def test_json_logging_redacts_compound_secret_keys_in_mapping_arguments() -> None:
    from apyra.observability.logging import JsonFormatter

    formatter = JsonFormatter()
    message = formatter.format(
        logging.makeLogRecord(
            {
                "msg": "credentials=%s",
                "args": (
                    {
                        "client_secret": "client-secret-value",
                        "access_token": "access-token-value",
                        "api-key": "api-key-value",
                        "nested": {"refresh_token": "refresh-token-value"},
                        "status": "ready",
                    },
                ),
                "levelname": "INFO",
                "name": "test",
            }
        )
    )

    assert json.loads(message)["message"] == (
        "credentials={'client_secret': '***REDACTED***', "
        "'access_token': '***REDACTED***', 'api-key': '***REDACTED***', "
        "'nested': {'refresh_token': '***REDACTED***'}, 'status': 'ready'}"
    )


def test_json_logging_redacts_serialized_credentials_and_normalized_cookie_keys() -> None:
    from apyra.observability.logging import JsonFormatter

    formatter = JsonFormatter()
    serialized = formatter.format(
        logging.makeLogRecord(
            {
                "msg": json.dumps(
                    {
                        "password": 'json password "with quotes" secret',
                        "access_token": "json-access-token-secret",
                        "client_secret": "json-client-secret",
                    }
                ),
                "levelname": "INFO",
                "name": "test",
            }
        )
    )
    cookie_mapping = formatter.format(
        logging.makeLogRecord(
            {
                "msg": "headers=%s",
                "args": ({"set_cookie": "session=normalized-cookie-secret; HttpOnly"},),
                "levelname": "INFO",
                "name": "test",
            }
        )
    )
    cookie_list = formatter.format(
        logging.makeLogRecord(
            {
                "msg": "headers=%s",
                "args": ({"set_cookie": ["session=list-cookie-secret; HttpOnly"]},),
                "levelname": "INFO",
                "name": "test",
            }
        )
    )
    named_cookie = formatter.format(
        logging.makeLogRecord(
            {
                "msg": "header=%(set_cookie)s",
                "args": {"set_cookie": 'session="quoted-named-cookie-secret"; HttpOnly'},
                "levelname": "INFO",
                "name": "test",
            }
        )
    )

    assert all(
        secret not in serialized + cookie_mapping + cookie_list + named_cookie
        for secret in (
            'json password "with quotes" secret',
            "json-access-token-secret",
            "json-client-secret",
            "normalized-cookie-secret",
            "list-cookie-secret",
            "named-cookie-secret",
            "quoted-named-cookie-secret",
        )
    )
