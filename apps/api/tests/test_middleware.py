import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.core.middleware import RateLimitMiddleware, RequestIDMiddleware
from app.core.rate_limit import FixedWindowRateLimiter

# ── FixedWindowRateLimiter (pure unit tests, deterministic fake clock) ──


def test_allows_up_to_the_limit_within_the_window(monkeypatch):
    fake_now = [0.0]
    monkeypatch.setattr("app.core.rate_limit.time.monotonic", lambda: fake_now[0])
    limiter = FixedWindowRateLimiter(max_requests=3, window_seconds=60.0)

    for _ in range(3):
        allowed, _ = limiter.check("client-a")
        assert allowed is True

    allowed, retry_after = limiter.check("client-a")
    assert allowed is False
    assert retry_after > 0


def test_rejected_request_does_not_itself_count_against_the_window(monkeypatch):
    fake_now = [0.0]
    monkeypatch.setattr("app.core.rate_limit.time.monotonic", lambda: fake_now[0])
    limiter = FixedWindowRateLimiter(max_requests=1, window_seconds=60.0)

    assert limiter.check("client-a")[0] is True
    assert limiter.check("client-a")[0] is False
    assert limiter.check("client-a")[0] is False  # still rejected, not accidentally allowed on 2nd try


def test_window_expiry_allows_requests_again(monkeypatch):
    fake_now = [0.0]
    monkeypatch.setattr("app.core.rate_limit.time.monotonic", lambda: fake_now[0])
    limiter = FixedWindowRateLimiter(max_requests=1, window_seconds=60.0)

    assert limiter.check("client-a")[0] is True
    assert limiter.check("client-a")[0] is False

    fake_now[0] = 61.0  # past the window
    assert limiter.check("client-a")[0] is True


def test_different_keys_have_independent_limits(monkeypatch):
    fake_now = [0.0]
    monkeypatch.setattr("app.core.rate_limit.time.monotonic", lambda: fake_now[0])
    limiter = FixedWindowRateLimiter(max_requests=1, window_seconds=60.0)

    assert limiter.check("client-a")[0] is True
    assert limiter.check("client-b")[0] is True  # independent key, not affected by client-a


# ── Middleware, end-to-end over real HTTP against a minimal throwaway app ──
# (the production `app` singleton locks its middleware stack in at import
# time based on settings.rate_limit_enabled, which conftest.py sets False
# for the whole suite — so real 429/request-ID HTTP behavior is verified
# against a small dedicated app here, not by fighting that lock-in.)


def _build_test_app(*, rate_limited: bool) -> Starlette:
    async def ok(request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/ping", ok)])
    if rate_limited:
        app.add_middleware(
            RateLimitMiddleware,
            general_limiter=FixedWindowRateLimiter(max_requests=2, window_seconds=60.0),
            auth_limiter=FixedWindowRateLimiter(max_requests=1, window_seconds=60.0),
        )
    app.add_middleware(RequestIDMiddleware)
    return app


@pytest.fixture
async def rate_limited_client():
    transport = ASGITransport(app=_build_test_app(rate_limited=True))
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_request_id_header_is_always_present(rate_limited_client: AsyncClient):
    response = await rate_limited_client.get("/ping")
    assert response.status_code == 200
    assert "x-request-id" in response.headers
    # A real, freshly-generated UUID when the client didn't supply one.
    uuid.UUID(response.headers["x-request-id"])


async def test_a_valid_client_supplied_request_id_is_echoed_back(rate_limited_client: AsyncClient):
    supplied = str(uuid.uuid4())
    response = await rate_limited_client.get("/ping", headers={"X-Request-ID": supplied})
    assert response.headers["x-request-id"] == supplied


async def test_an_invalid_client_supplied_request_id_is_replaced_not_trusted(rate_limited_client: AsyncClient):
    response = await rate_limited_client.get("/ping", headers={"X-Request-ID": "not-a-uuid\r\nfake: log line"})
    # Never echoes the malformed value back — proves it was replaced, not
    # trusted verbatim (the actual log-injection risk this guards against).
    assert response.headers["x-request-id"] != "not-a-uuid\r\nfake: log line"
    uuid.UUID(response.headers["x-request-id"])


async def test_exceeding_the_general_limit_returns_429_with_retry_after(rate_limited_client: AsyncClient):
    for _ in range(2):
        response = await rate_limited_client.get("/ping")
        assert response.status_code == 200

    response = await rate_limited_client.get("/ping")
    assert response.status_code == 429
    assert "retry-after" in response.headers
    assert response.json()["detail"]


async def test_requests_under_the_limit_are_unaffected(rate_limited_client: AsyncClient):
    response = await rate_limited_client.get("/ping")
    assert response.status_code == 200


# ── Wired into the real app ──────────────────────────────────────────────


async def test_real_app_responses_carry_a_request_id(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    uuid.UUID(response.headers["x-request-id"])


async def test_unhandled_exception_returns_a_sanitized_response_with_the_request_id(
    client: AsyncClient, monkeypatch
):
    """A genuinely unexpected exception (not a typed domain error any
    router already catches) must never leak its own message to the
    client — only a generic message plus a request_id to correlate with
    the server-side log line that does have the real exception."""
    from app.domains.market_data import service as market_service

    async def _broken(*args, **kwargs):
        raise RuntimeError("some internal detail that must never reach the client")

    monkeypatch.setattr(market_service, "list_securities", _broken)

    response = await client.get("/api/v1/market/securities")
    assert response.status_code == 500
    body = response.json()
    assert body["detail"] == "Internal server error."
    assert "some internal detail" not in response.text
    assert body["request_id"] == response.headers["x-request-id"]
    uuid.UUID(body["request_id"])


async def test_existing_typed_http_exceptions_are_unaffected_by_the_catch_all_handler(
    client: AsyncClient, auth_headers: dict
):
    """The catch-all Exception handler must never shadow FastAPI's own
    handling of a deliberately-raised HTTPException — a 404 for an
    unknown symbol must still be a real 404 with its real detail message,
    not swallowed into a generic 500."""
    response = await client.get("/api/v1/corporate-actions/NOTASYMBOL", headers=auth_headers)
    assert response.status_code == 404
    assert "NOTASYMBOL" in response.json()["detail"]
