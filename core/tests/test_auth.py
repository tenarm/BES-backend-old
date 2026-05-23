import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from core.router import seed_roles, seed_admin_user
from core.models import User
from sqlmodel import select

@pytest.mark.asyncio
async def test_seed_and_login(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    """Verifies seeding default roles/users, logging in, and retrieving current user profile."""
    # Set the admin password in the environment for seeding
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "testpass123")
    
    # 1. Run core seed operations on the test database
    await seed_roles(db_session)
    await seed_admin_user(db_session)
    
    # Verify the admin user was correctly seeded in the database
    result = await db_session.execute(select(User).where(User.username == "admin"))
    admin = result.scalars().first()
    assert admin is not None
    assert admin.username == "admin"
    assert admin.is_superuser is True

    # 2. Attempt login using oauth2 password form data structure
    login_data = {
        "username": "admin",
        "password": "testpass123"
    }
    response = await client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 200
    
    tokens = response.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"
    
    # 3. Access current user profile using the retrieved JWT bearer token
    access_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    me_response = await client.get("/api/v1/auth/me", headers=headers)
    assert me_response.status_code == 200
    
    profile = me_response.json()
    assert profile["username"] == "admin"
    assert profile["is_superuser"] is True
