"""Keep short-lived playback credentials out of HTTP access logs."""

import logging
import re


_SENSITIVE_QUERY = re.compile(r"(?i)([?&](?:token|video_token|access_token|refresh_token|reset_token|x-amz-signature|x-amz-credential|x-amz-security-token)=)[^&\s]*")


class RedactAccessTokenFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple) and len(record.args) >= 3 and isinstance(record.args[2], str):
            path = record.args[2]
            redacted = _SENSITIVE_QUERY.sub(r"\1[REDACTED]", path)
            if redacted != path:
                record.args = (*record.args[:2], redacted, *record.args[3:])
        return True
