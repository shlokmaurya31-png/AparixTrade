"""Request-ID and rate-limit ASGI middleware (Tier 1 §42).

Both are plain Starlette middleware, not third-party packages — small
enough to own directly, and this app already follows that pattern for
everything else (e.g. the hand-rolled point-in-time query logic across
five domains) rather than reaching for a dependency for something this
scoped.
"""

import logging
import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.rate_limit import FixedWindowRateLimiter
from app.core.request_context import request_id_var

logger = logging.getLogger("app.request")

# Only accepted from an incoming X-Request-ID header if it's actually a
# UUID — an arbitrary client-supplied string would otherwise flow straight
# into structured log lines (core/logging_config.py), a real log-injection
# risk (e.g. a header containing embedded newlines/fake log entries) for a
# value with no other validation.
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

_AUTH_PATHS = {"/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/refresh"}


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assigns every request a real correlation ID: reused from a valid
    incoming X-Request-ID header (letting a caller correlate its own logs
    with this server's), otherwise freshly generated. Available to any
    logger call made while handling the request via request_id_var, and
    echoed back as a response header so a client/support ticket can quote
    it."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get("x-request-id")
        request_id = incoming if incoming and _UUID_RE.match(incoming) else str(uuid.uuid4())

        token = request_id_var.set(request_id)
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)

        response.headers["X-Request-ID"] = request_id
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Real per-client-IP rate limiting — a stricter window for
    auth endpoints (login/register/refresh — the brute-force-relevant
    ones) than everything else. `request.client.host` is used directly,
    not an X-Forwarded-For header — correct for this app's actual
    deployment (no reverse proxy in front of it); a real production
    deployment behind one would need to read a specifically-trusted
    forwarded-for header instead of blindly trusting a client-supplied
    one, which is its own real security decision, not made here."""

    def __init__(self, app, *, general_limiter: FixedWindowRateLimiter, auth_limiter: FixedWindowRateLimiter) -> None:
        super().__init__(app)
        self.general_limiter = general_limiter
        self.auth_limiter = auth_limiter

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        is_auth_path = request.url.path in _AUTH_PATHS
        limiter = self.auth_limiter if is_auth_path else self.general_limiter
        key = f"{'auth' if is_auth_path else 'general'}:{client_ip}"

        allowed, retry_after = limiter.check(key)
        if not allowed:
            logger.warning("Rate limit exceeded for %s on %s", client_ip, request.url.path)
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again shortly."},
                headers={"Retry-After": str(int(retry_after) + 1)},
            )

        return await call_next(request)
