import pytest
import uuid
from httpx import AsyncClient
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.models import User, Role
from core.rbac import require_permission
from core.auth import create_access_token, get_password_hash


@pytest.fixture(autouse=True)
def add_test_routes(test_app: FastAPI):
    """Add dedicated test routes to test_app to verify require_permission gates."""
    @test_app.get(
        "/api/v1/test-perm-read",
        dependencies=[Depends(require_permission("test:resource:read"))]
    )
    async def test_perm_read():
        return {"status": "success", "message": "allowed"}

    @test_app.post(
        "/api/v1/test-perm-write",
        dependencies=[Depends(require_permission("test:resource:write"))]
    )
    async def test_perm_write():
        return {"status": "success", "message": "allowed"}


@pytest.mark.asyncio
async def test_rbac_superuser_access(client: AsyncClient, db_session: AsyncSession):
    """Verifies that a superuser automatically bypasses all RBAC permission gates."""
    # 1. Create a superuser in the test database
    superuser = User(
        id=uuid.uuid4(),
        username="superadmin",
        email="superadmin@example.com",
        hashed_password=get_password_hash("supersecure123"),
        is_active=True,
        is_superuser=True,
        role_id=None
    )
    db_session.add(superuser)
    await db_session.commit()
    await db_session.refresh(superuser)

    # 2. Generate an access token for the superuser
    token = create_access_token({"sub": superuser.username})
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Verify they can access read-protected endpoint
    read_res = await client.get("/api/v1/test-perm-read", headers=headers)
    assert read_res.status_code == 200
    assert read_res.json()["status"] == "success"

    # 4. Verify they can access write-protected endpoint
    write_res = await client.post("/api/v1/test-perm-write", headers=headers)
    assert write_res.status_code == 200
    assert write_res.json()["status"] == "success"


@pytest.mark.asyncio
async def test_rbac_granular_permissions(client: AsyncClient, db_session: AsyncSession):
    """Verifies regular users are allowed or blocked dynamically based on their role permissions."""
    # 1. Create a Role with only READ permissions
    read_role = Role(
        id=uuid.uuid4(),
        name="readonly_viewer",
        description="Can only read resource",
        permissions={
            "test": {
                "resource": {
                    "read": True,
                    "write": False
                }
            }
        }
    )
    db_session.add(read_role)
    await db_session.commit()
    await db_session.refresh(read_role)

    # 2. Create a standard User with this role
    regular_user = User(
        id=uuid.uuid4(),
        username="viewer",
        email="viewer@example.com",
        hashed_password=get_password_hash("viewpassword"),
        is_active=True,
        is_superuser=False,
        role_id=read_role.id
    )
    db_session.add(regular_user)
    await db_session.commit()
    await db_session.refresh(regular_user)

    # 3. Generate access token
    token = create_access_token({"sub": regular_user.username})
    headers = {"Authorization": f"Bearer {token}"}

    # 4. Assert allowed access to read-protected endpoint
    read_res = await client.get("/api/v1/test-perm-read", headers=headers)
    assert read_res.status_code == 200
    assert read_res.json()["status"] == "success"

    # 5. Assert blocked access to write-protected endpoint (returns 403 Forbidden)
    write_res = await client.post("/api/v1/test-perm-write", headers=headers)
    assert write_res.status_code == 403
    assert "Permission denied" in write_res.json()["detail"]


@pytest.mark.asyncio
async def test_rbac_denied_without_role(client: AsyncClient, db_session: AsyncSession):
    """Verifies that standard users without any assigned role are blocked by default."""
    # 1. Create a user with no role ID
    user_no_role = User(
        id=uuid.uuid4(),
        username="noroleuser",
        email="norole@example.com",
        hashed_password=get_password_hash("norolepass"),
        is_active=True,
        is_superuser=False,
        role_id=None
    )
    db_session.add(user_no_role)
    await db_session.commit()
    await db_session.refresh(user_no_role)

    # 2. Generate access token
    token = create_access_token({"sub": user_no_role.username})
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Verify read access is blocked
    read_res = await client.get("/api/v1/test-perm-read", headers=headers)
    assert read_res.status_code == 403
    assert "no role assigned" in read_res.json()["detail"]

