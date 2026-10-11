import logging

from app.core.access_log import RedactAccessTokenFilter


def test_access_log_filter_redacts_playback_token_without_changing_other_query():
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1", "GET", "/api/v1/stream?token=secret-value&quality=720p", "1.1", 206),
        None,
    )
    assert RedactAccessTokenFilter().filter(record)
    message = record.getMessage()
    assert "secret-value" not in message
    assert "token=[REDACTED]&quality=720p" in message
