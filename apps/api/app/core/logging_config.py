"""Structured console logging with per-request correlation (Tier 1 §42).

Before this, `app.*` loggers (e.g. domains/news/service.py's
`logger.exception(...)` calls, which already existed) had no explicit
handler — Python's root logger falls back to a bare "handler of last
resort" that prints ERROR+ with no timestamp, level, or logger name, and
WARNING-level calls print nothing at all. This attaches a real handler to
the root logger (uvicorn's own "uvicorn"/"uvicorn.access"/"uvicorn.error"
loggers are unaffected — uvicorn configures those directly, not through
root) with a formatter that includes the request ID every log call made
during a request now carries (request_context.py), so a specific request's
log lines can be grepped out even under concurrent traffic.
"""

import logging

from app.core.request_context import request_id_var


class RequestIDLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s")
    )
    handler.addFilter(RequestIDLogFilter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
