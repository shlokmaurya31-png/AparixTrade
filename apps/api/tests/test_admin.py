import os
import uuid

from httpx import AsyncClient


async def test_admin_routes_reject_non_admin_user(client: AsyncClient, auth_headers: dict):
    for path in ["/api/v1/admin/users", "/api/v1/admin/audit-logs", "/api/v1/admin/ai-usage", "/api/v1/admin/system-health"]:
        response = await client.get(path, headers=auth_headers)
        assert response.status_code == 403, path


async def test_admin_routes_reject_unauthenticated_requests(client: AsyncClient):
    response = await client.get("/api/v1/admin/users")
    assert response.status_code == 401


async def test_me_reports_is_admin_false_for_normal_user(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.json()["is_admin"] is False


async def test_admin_email_allowlist_grants_access(client: AsyncClient, monkeypatch):
    from app.core import config

    admin_email = f"admin-{uuid.uuid4().hex}@example.com"
    monkeypatch.setenv("ADMIN_EMAILS", admin_email)
    config.get_settings.cache_clear()

    register = await client.post(
        "/api/v1/auth/register",
        json={"email": admin_email, "password": "correct-horse-battery", "full_name": "Admin User"},
    )
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    me = await client.get("/api/v1/auth/me", headers=headers)
    assert me.json()["is_admin"] is True

    health = await client.get("/api/v1/admin/system-health", headers=headers)
    assert health.status_code == 200
    assert health.json()["users_count"] >= 1

    config.get_settings.cache_clear()
