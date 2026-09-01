import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.core.roles import ALL_ROLES, DEFAULT_ROLE, Role
from app.models.user import User


async def test_new_user_defaults_to_user_role(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.json()["role"] == DEFAULT_ROLE == "user"
    assert response.json()["is_admin"] is False


async def test_all_roles_are_the_six_named_in_the_spec():
    assert set(ALL_ROLES) == {"super_admin", "admin", "compliance", "analyst", "support", "user"}


async def test_stored_admin_role_grants_admin_routes_without_email_allowlist(client: AsyncClient):
    email = f"role-admin-{uuid.uuid4().hex}@example.com"
    register = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "correct-horse-battery", "full_name": "Role Admin"}
    )
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    # Not in ADMIN_EMAILS — stored role is the only thing granting access here.
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        user.role = Role.ADMIN
        await db.commit()

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["is_admin"] is True
    assert me.json()["role"] == "admin"

    health = await client.get("/api/v1/admin/system-health", headers=headers)
    assert health.status_code == 200


async def test_super_admin_role_also_grants_admin_routes(client: AsyncClient):
    email = f"role-superadmin-{uuid.uuid4().hex}@example.com"
    register = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "correct-horse-battery", "full_name": "Super Admin"}
    )
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        user.role = Role.SUPER_ADMIN
        await db.commit()

    health = await client.get("/api/v1/admin/system-health", headers=headers)
    assert health.status_code == 200


async def test_non_admin_roles_do_not_grant_admin_routes(client: AsyncClient):
    email = f"role-analyst-{uuid.uuid4().hex}@example.com"
    register = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "correct-horse-battery", "full_name": "Analyst"}
    )
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        user.role = Role.ANALYST
        await db.commit()

    health = await client.get("/api/v1/admin/system-health", headers=headers)
    assert health.status_code == 403


async def test_admin_emails_allowlist_still_works_without_a_stored_admin_role(client: AsyncClient, monkeypatch):
    from app.core import config

    admin_email = f"allowlist-admin-{uuid.uuid4().hex}@example.com"
    monkeypatch.setenv("ADMIN_EMAILS", admin_email)
    config.get_settings.cache_clear()
    try:
        register = await client.post(
            "/api/v1/auth/register",
            json={"email": admin_email, "password": "correct-horse-battery", "full_name": "Allowlist Admin"},
        )
        headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

        # Stored role is still the untouched default — access comes purely
        # from the allowlist, exactly as it did before Tier 1.
        async with AsyncSessionLocal() as db:
            user = (await db.execute(select(User).where(User.email == admin_email))).scalar_one()
            assert user.role == DEFAULT_ROLE

        health = await client.get("/api/v1/admin/system-health", headers=headers)
        assert health.status_code == 200
    finally:
        config.get_settings.cache_clear()
