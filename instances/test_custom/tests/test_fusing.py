import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from core.router import seed_roles, seed_admin_user
from core.models import User
from sqlmodel import select

@pytest.mark.asyncio
async def test_instance_fusion_startup(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    """Verify that all licensed extension router paths successfully load on boot and return valid responses."""
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "testpass123")
    await seed_roles(db_session)
    await seed_admin_user(db_session)

    # 1. Login to get access token
    login_data = {
        "username": "admin",
        "password": "testpass123"
    }
    response = await client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 200
    access_token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # 2. Test GET /api/v1/settings/profile (provisions default company profile)
    profile_res = await client.get("/api/v1/settings/profile", headers=headers)
    assert profile_res.status_code == 200
    pdata = profile_res.json()["data"]
    assert pdata["name"] == "Default Corporate Entity"
    assert pdata["base_currency"] == "USD"
    assert pdata["version_id"] == 1

    # 3. Test PATCH /api/v1/settings/profile (updates details, increments version)
    update_payload = {
        "name": "Acme Holdings Corp",
        "legal_name": "Acme Holdings LLC",
        "registration_id": "EIN-9998887",
        "version_id": 1
    }
    update_res = await client.patch("/api/v1/settings/profile", json=update_payload, headers=headers)
    assert update_res.status_code == 200
    updated_pdata = update_res.json()["data"]
    assert updated_pdata["name"] == "Acme Holdings Corp"
    assert updated_pdata["version_id"] == 2

    # 4. Test Concurrency Exception on PATCH with stale version_id (returns 409)
    conflict_payload = {
        "name": "Acme Conflict",
        "legal_name": "Acme Holdings LLC",
        "version_id": 1  # Stale version
    }
    conflict_res = await client.patch("/api/v1/settings/profile", json=conflict_payload, headers=headers)
    assert conflict_res.status_code == 409

    # 5. Test POST /api/v1/settings/subsidiaries
    sub_payload = {
        "name": "Acme UK",
        "legal_name": "Acme UK Ltd",
        "tax_id": "GB123456789",
        "country_code": "GB",
        "currency_code": "GBP"
    }
    sub_res = await client.post("/api/v1/settings/subsidiaries", json=sub_payload, headers=headers)
    assert sub_res.status_code == 200
    sub_data = sub_res.json()["data"]
    assert sub_data["name"] == "Acme UK"
    assert sub_data["currency_code"] == "GBP"

    # 6. Test GET /api/v1/settings/subsidiaries (returns paginated subsidiaries)
    list_res = await client.get("/api/v1/settings/subsidiaries", headers=headers)
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["metadata"]["total"] >= 1
    assert any(s["name"] == "Acme UK" for s in list_data["data"])
