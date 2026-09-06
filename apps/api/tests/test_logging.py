import json
import logging

from app.core.logging import JsonFormatter


def test_json_logs_are_structured_and_ignore_unapproved_fields() -> None:
    record = logging.LogRecord(
        name="app.markets.http",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="market_request",
        args=(),
        exc_info=None,
    )
    record.component = "market_http"
    record.market = "SKINPORT"
    record.status = 200
    record.duration = 12.5
    record.authorization = "secret-that-must-not-be-serialized"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "market_request"
    assert payload["component"] == "market_http"
    assert payload["market"] == "SKINPORT"
    assert payload["duration"] == 12.5
    assert "authorization" not in payload
    assert "secret-that-must-not-be-serialized" not in json.dumps(payload)
