import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.core.roles import Role
from app.models.audit import AuditLog
from app.models.user import User


async def _register(client: AsyncClient, label: str) -> tuple[str, dict]:
    email = f"role-mgmt-{label}-{uuid.uuid4().hex}@example.com"
    register = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "correct-horse-battery", "full_name": label}
    )
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}
    return email, headers


async def _set_role(email: str, role: str) -> None:
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        user.role = role
        await db.commit()


async def _user_id(email: str) -> str:
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        return str(user.id)


# ── Happy path ───────────────────────────────────────────────────────────


async def test_admin_can_change_another_users_role(client: AsyncClient):
    admin_email, admin_headers = await _register(client, "admin")
    await _set_role(admin_email, Role.ADMIN)

    target_email, _ = await _register(client, "target")
    target_id = await _user_id(target_email)

    response = await client.patch(
        f"/api/v1/admin/users/{target_id}/role", json={"role": "analyst"}, headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json()["role"] == "analyst"

    async with AsyncSessionLocal() as db:
        target = (await db.execute(select(User).where(User.email == target_email))).scalar_one()
        assert target.role == "analyst"


async def test_role_change_is_recorded_in_the_audit_log(client: AsyncClient):
    admin_email, admin_headers = await _register(client, "admin-audit")
    await _set_role(admin_email, Role.ADMIN)
    target_email, _ = await _register(client, "target-audit")
    target_id = await _user_id(target_email)

    await client.patch(f"/api/v1/admin/users/{target_id}/role", json={"role": "compliance"}, headers=admin_headers)

    async with AsyncSessionLocal() as db:
        logs = (
            await db.execute(select(AuditLog).where(AuditLog.action == "admin.update_user_role"))
        ).scalars().all()
    matching = [log for log in logs if log.input_data.get("target_user_id") == target_id]
    assert len(matching) == 1
    assert matching[0].input_data["new_role"] == "compliance"
    assert matching[0].input_data["old_role"] == "user"


async def test_get_users_includes_role(client: AsyncClient):
    admin_email, admin_headers = await _register(client, "admin-list")
    await _set_role(admin_email, Role.ADMIN)

    response = await client.get("/api/v1/admin/users", headers=admin_headers)
    assert response.status_code == 200
    assert all("role" in u for u in response.json())


# ── Guards ───────────────────────────────────────────────────────────────


async def test_cannot_change_own_role(client: AsyncClient):
    admin_email, admin_headers = await _register(client, "self")
    await _set_role(admin_email, Role.ADMIN)
    admin_id = await _user_id(admin_email)

    response = await client.patch(
        f"/api/v1/admin/users/{admin_id}/role", json={"role": "analyst"}, headers=admin_headers
    )
    assert response.status_code == 400


async def test_plain_admin_cannot_grant_super_admin(client: AsyncClient):
    admin_email, admin_headers = await _register(client, "notsuper")
    await _set_role(admin_email, Role.ADMIN)
    target_email, _ = await _register(client, "wannabe-super")
    target_id = await _user_id(target_email)

    response = await client.patch(
        f"/api/v1/admin/users/{target_id}/role", json={"role": "super_admin"}, headers=admin_headers
    )
    assert response.status_code == 403

    async with AsyncSessionLocal() as db:
        target = (await db.execute(select(User).where(User.email == target_email))).scalar_one()
        assert target.role != "super_admin"


async def test_plain_admin_cannot_change_an_existing_super_admins_role(client: AsyncClient):
    admin_email, admin_headers = await _register(client, "notsuper2")
    await _set_role(admin_email, Role.ADMIN)
    super_email, _ = await _register(client, "existing-super")
    await _set_role(super_email, Role.SUPER_ADMIN)
    super_id = await _user_id(super_email)

    response = await client.patch(
        f"/api/v1/admin/users/{super_id}/role", json={"role": "analyst"}, headers=admin_headers
    )
    assert response.status_code == 403


async def test_super_admin_can_grant_super_admin(client: AsyncClient):
    super_email, super_headers = await _register(client, "granting-super")
    await _set_role(super_email, Role.SUPER_ADMIN)
    target_email, _ = await _register(client, "promoted")
    target_id = await _user_id(target_email)

    response = await client.patch(
        f"/api/v1/admin/users/{target_id}/role", json={"role": "super_admin"}, headers=super_headers
    )
    assert response.status_code == 200
    assert response.json()["role"] == "super_admin"


async def test_unknown_role_is_rejected(client: AsyncClient):
    admin_email, admin_headers = await _register(client, "admin-badrole")
    await _set_role(admin_email, Role.ADMIN)
    target_email, _ = await _register(client, "target-badrole")
    target_id = await _user_id(target_email)

    response = await client.patch(
        f"/api/v1/admin/users/{target_id}/role", json={"role": "dictator"}, headers=admin_headers
    )
    assert response.status_code == 422


async def test_role_update_for_unknown_user_is_404(client: AsyncClient):
    admin_email, admin_headers = await _register(client, "admin-404")
    await _set_role(admin_email, Role.ADMIN)

    response = await client.patch(
        f"/api/v1/admin/users/{uuid.uuid4()}/role", json={"role": "analyst"}, headers=admin_headers
    )
    assert response.status_code == 404


async def test_non_admin_cannot_reach_role_update_endpoint(client: AsyncClient, auth_headers: dict):
    other_email, _ = await _register(client, "target-nonadmin")
    other_id = await _user_id(other_email)

    response = await client.patch(
        f"/api/v1/admin/users/{other_id}/role", json={"role": "analyst"}, headers=auth_headers
    )
    assert response.status_code == 403
