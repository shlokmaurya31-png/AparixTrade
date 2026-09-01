import os
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient

TEST_DB_PATH = Path(__file__).parent / f"test_{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_PATH}"
os.environ["AI_PROVIDER"] = "mock"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["BROKER_PROVIDER"] = "mock"
os.environ["BROKER_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

from app.main import app, lifespan  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _cleanup_db():
    yield
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest_asyncio.fixture
async def client():
    async with lifespan(app):
        transport = ASGITransport(app=app)
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
