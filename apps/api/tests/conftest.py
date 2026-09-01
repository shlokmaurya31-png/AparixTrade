import os
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient

TEST_DB_PATH = Path(__file__).parent / f"test_{uuid.uuid4().hex}.db"
# setdefault, not unconditional assignment: lets `DATABASE_URL=postgresql+asyncpg://...
# uv run pytest` run this exact suite against a real Postgres instance
# (docs/DATABASE_MIGRATION.md's own "re-run the full suite before trusting
# it" step) without touching this file. No effect on the normal case —
# nothing else sets DATABASE_URL before importing this module.
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{TEST_DB_PATH}")
os.environ["AI_PROVIDER"] = "mock"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["BROKER_PROVIDER"] = "mock"
os.environ["BROKER_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
# The test suite makes hundreds of requests from one fake client IP —
# real rate limiting is tested directly against FixedWindowRateLimiter/
# RateLimitMiddleware (tests/test_middleware.py), not through this shared
# client fixture, which would otherwise start getting real 429s partway
# through an unrelated test file.
os.environ["RATE_LIMIT_ENABLED"] = "false"

from app.main import app, lifespan  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _cleanup_db():
    yield
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest_asyncio.fixture
async def client():
    async with lifespan(app):
        # raise_app_exceptions=False: a real HTTP client never sees a
        # Python traceback, only a response — and since main.py's global
        # exception handler now converts any genuinely unhandled exception
        # into a real (sanitized) 500 response, that's what the test
        # client should see too, not a re-raised exception escaping into
        # the test itself.
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict:
    email = f"{uuid.uuid4().hex}@example.com"
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-battery", "full_name": "Test User"},
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
