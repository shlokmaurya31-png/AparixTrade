import uuid

from httpx import AsyncClient


async def test_register_login_me_roundtrip(client: AsyncClient):
    email = f"{uuid.uuid4().hex}@example.com"

    register = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct-horse-battery", "full_name": "Aparix Tester"},
    )
    assert register.status_code == 201
    tokens = register.json()
    assert "access_token" in tokens and "refresh_token" in tokens

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "correct-horse-battery"})
    assert login.status_code == 200

    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == email
    assert body["preferences"]["complexity_level"] == 1  # default onboarding level


async def test_duplicate_email_registration_is_rejected(client: AsyncClient):
    email = f"{uuid.uuid4().hex}@example.com"
    payload = {"email": email, "password": "correct-horse-battery", "full_name": "Dup User"}

    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


async def test_wrong_password_is_rejected(client: AsyncClient):
    email = f"{uuid.uuid4().hex}@example.com"
    await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "correct-horse-battery", "full_name": "X"}
    )

    login = await client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password"})
    assert login.status_code == 401


async def test_me_requires_auth(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
