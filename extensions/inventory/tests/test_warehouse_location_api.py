import pytest
import uuid
from decimal import Decimal
from httpx import AsyncClient
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.auth import get_current_user
from core.models import User
from inventory.models import InventoryWarehouseLocation


import pytest_asyncio


@pytest.fixture
def mock_admin_user() -> User:
    """Fixture to return a superuser for bypassing permission checks."""
    return User(
        id=uuid.uuid4(),
        username="admin_tester",
        is_superuser=True,
        is_active=True
    )


@pytest.fixture
def api_test_app(test_app: FastAPI, mock_admin_user: User) -> FastAPI:
    """Fixture to override get_current_user to return a mock superuser."""
    test_app.dependency_overrides[get_current_user] = lambda: mock_admin_user
    return test_app


@pytest_asyncio.fixture
async def api_client(api_test_app: FastAPI) -> AsyncClient:
    """Fixture to return an AsyncClient targeting the api_test_app."""
    from httpx import ASGITransport
    async with AsyncClient(transport=ASGITransport(app=api_test_app), base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_api_create_location_success(api_client: AsyncClient, db_session: AsyncSession):
    # 1. POST request to create a location
    payload = {
        "code": "WH-API-1",
        "name": "API Warehouse 1",
        "type": "WAREHOUSE",
        "max_volume": "250.0000",
        "max_weight": "1000.0000",
        "address": "123 API Way"
    }
    
    response = await api_client.post("/api/v1/inventory/locations", json=payload)
    assert response.status_code == 200
    
    res_data = response.json()
    assert res_data["status"] == "success"
    data = res_data["data"]
    assert data["code"] == "WH-API-1"
    assert data["type"] == "WAREHOUSE"
    assert Decimal(data["max_volume"]) == Decimal("250.0000")
    
    # 2. Check DB directly
    stmt = select(InventoryWarehouseLocation).where(InventoryWarehouseLocation.code == "WH-API-1")
    loc = (await db_session.execute(stmt)).scalar()
    assert loc is not None
    assert loc.name == "API Warehouse 1"


@pytest.mark.asyncio
async def test_api_list_and_details_locations(api_client: AsyncClient, db_session: AsyncSession):
    # 1. Create a couple of locations directly in DB
    loc1 = InventoryWarehouseLocation(
        code="WH-API-A",
        name="API Warehouse A",
        type="WAREHOUSE",
        max_volume=Decimal("100.0"),
        max_weight=Decimal("500.0")
    )
    loc2 = InventoryWarehouseLocation(
        code="WH-API-B",
        name="API Warehouse B",
        type="WAREHOUSE",
        max_volume=Decimal("200.0"),
        max_weight=Decimal("800.0")
    )
    db_session.add(loc1)
    db_session.add(loc2)
    await db_session.commit()
    await db_session.refresh(loc1)
    await db_session.refresh(loc2)
    
    # 2. List locations via API
    response = await api_client.get("/api/v1/inventory/locations")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    locations = res_data["data"]
    
    # Check that loc1 and loc2 are listed
    codes = [l["code"] for l in locations]
    assert "WH-API-A" in codes
    assert "WH-API-B" in codes
    
    # 3. Get details of loc1
    detail_response = await api_client.get(f"/api/v1/inventory/locations/{loc1.id}")
    assert detail_response.status_code == 200
    detail_data = detail_response.json()
    assert detail_data["status"] == "success"
    assert detail_data["data"]["code"] == "WH-API-A"
    assert detail_data["data"]["name"] == "API Warehouse A"


@pytest.mark.asyncio
async def test_api_update_location(api_client: AsyncClient, db_session: AsyncSession):
    # 1. Create a location directly in DB
    loc = InventoryWarehouseLocation(
        code="WH-API-UP",
        name="API Update Warehouse",
        type="WAREHOUSE",
        version_id=1
    )
    db_session.add(loc)
    await db_session.commit()
    await db_session.refresh(loc)
    
    # 2. Update name using PUT
    payload = {
        "name": "API Update Warehouse (Modified)"
    }
    # Version_id must be sent as query parameter
    response = await api_client.put(
        f"/api/v1/inventory/locations/{loc.id}?version_id=1",
        json=payload
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    assert res_data["data"]["name"] == "API Update Warehouse (Modified)"
    assert res_data["data"]["version_id"] == 2
    
    # Stale version update check (optimistic concurrency lock)
    response_stale = await api_client.put(
        f"/api/v1/inventory/locations/{loc.id}?version_id=1",
        json=payload
    )
    assert response_stale.status_code == 409


@pytest.mark.asyncio
async def test_api_toggle_audit_lock(api_client: AsyncClient, db_session: AsyncSession):
    # 1. Create a location
    loc = InventoryWarehouseLocation(
        code="WH-API-LOCK",
        name="API Lock Warehouse",
        type="WAREHOUSE",
        audit_locked=False
    )
    db_session.add(loc)
    await db_session.commit()
    await db_session.refresh(loc)
    
    # 2. Lock it using PATCH
    response = await api_client.patch(f"/api/v1/inventory/locations/{loc.id}/audit-lock?locked=true")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    assert res_data["data"]["audit_locked"] is True
    
    # Verify in DB
    await db_session.refresh(loc)
    assert loc.audit_locked is True
    
    # 3. Unlock it using PATCH
    response_unlock = await api_client.patch(f"/api/v1/inventory/locations/{loc.id}/audit-lock?locked=false")
    assert response_unlock.status_code == 200
    assert response_unlock.json()["data"]["audit_locked"] is False
    
    # Verify in DB
    await db_session.refresh(loc)
    assert loc.audit_locked is False
