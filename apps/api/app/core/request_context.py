"""A per-request correlation ID, available to any logger call made while
handling a request — not just the top-level exception handler. Set by
RequestIDMiddleware (core/middleware.py) at the start of every request and
read by the logging filter (core/logging_config.py) on every log record.
"""

import contextvars

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
