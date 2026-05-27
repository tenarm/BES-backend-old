import pytest
import uuid
from decimal import Decimal
from unittest.mock import patch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from inventory.models import InventoryWarehouseLocation
from inventory.services import (
    WarehouseLocationService,
    InvalidCodeFormatError,
    CircularHierarchyError,
    ActiveStockLocationError,
    NegativeCapacityError,
    ConcurrencyError,
    ItemDomainException
)
from inventory.schemas import LocationCreate, LocationUpdate


@pytest.mark.asyncio
async def test_create_location_success(db_session: AsyncSession):
    # 1. Onboard a warehouse using service
    data = LocationCreate(
        code="WH-MAIN",
        name="Main Depot Warehouse",
        type="WAREHOUSE",
        max_volume=Decimal("1250.5000"),
        max_weight=Decimal("50000.0000"),
        address="100 Logistics Dr"
    )
    
    result = await WarehouseLocationService.create_location(db_session, data)
    
    # 2. Assertions
    assert result.code == "WH-MAIN"
    assert result.type == "WAREHOUSE"
    assert result.max_volume == Decimal("1250.5000")
    assert result.max_weight == Decimal("50000.0000")
    assert result.is_active is True
    
    # Assert DB persistence
    stmt = select(InventoryWarehouseLocation).where(InventoryWarehouseLocation.code == "WH-MAIN")
    loc = (await db_session.execute(stmt)).scalar()
    assert loc is not None
    assert loc.name == "Main Depot Warehouse"


@pytest.mark.asyncio
async def test_prevent_duplicate_location_code(db_session: AsyncSession):
    data1 = LocationCreate(
        code="WH-EAST",
        name="East Warehouse",
        type="WAREHOUSE"
    )
    await WarehouseLocationService.create_location(db_session, data1)

    # Try creating with duplicate code (case insensitive/trimmed check)
    data2 = LocationCreate(
        code=" wh-east ",
        name="East Warehouse Duplicate",
        type="WAREHOUSE"
    )
    with pytest.raises(ItemDomainException):
        await WarehouseLocationService.create_location(db_session, data2)


@pytest.mark.asyncio
async def test_prevent_circular_location_hierarchy(db_session: AsyncSession):
    # 1. Create WH-1
    wh1 = await WarehouseLocationService.create_location(
        db_session, 
        LocationCreate(code="WH-1", name="Warehouse One")
    )
    
    # 2. Create ZONE-1 as child of WH-1
    zone1 = await WarehouseLocationService.create_location(
        db_session, 
        LocationCreate(code="ZONE-1", name="Zone One", parent_id=wh1.id, type="ZONE")
    )
    
    # 3. Create BIN-1 as child of ZONE-1
    bin1 = await WarehouseLocationService.create_location(
        db_session, 
        LocationCreate(code="BIN-1", name="Bin One", parent_id=zone1.id, type="BIN")
    )
    
    # 4. Try updating WH-1 parent to BIN-1 (Creates loop WH-1 -> ZONE-1 -> BIN-1 -> WH-1)
    update_data = LocationUpdate(parent_id=bin1.id)
    with pytest.raises(CircularHierarchyError):
        await WarehouseLocationService.update_location(db_session, wh1.id, update_data, wh1.version_id)


@pytest.mark.asyncio
async def test_optimistic_concurrency_lock(db_session: AsyncSession):
    loc = await WarehouseLocationService.create_location(
        db_session, 
        LocationCreate(code="WH-CONC", name="Concurrency Warehouse")
    )
    version_id = loc.version_id

    # First update succeeds
    update1 = LocationUpdate(name="Warehouse Concurrency (Updated)")
    res1 = await WarehouseLocationService.update_location(db_session, loc.id, update1, version_id)
    assert res1.version_id == version_id + 1

    # Second update using stale version fails
    update2 = LocationUpdate(name="Warehouse Concurrency (Stale)")
    with pytest.raises(ConcurrencyError):
        await WarehouseLocationService.update_location(db_session, loc.id, update2, version_id)


@pytest.mark.asyncio
async def test_deactivate_gated_by_stock(db_session: AsyncSession):
    loc = await WarehouseLocationService.create_location(
        db_session, 
        LocationCreate(code="WH-STOCK", name="Stock Warehouse")
    )

    # Mock the helper function _has_stock_balance to return True
    with patch("inventory.services._has_stock_balance", return_value=True):
        update = LocationUpdate(is_active=False)
        with pytest.raises(ActiveStockLocationError):
            await WarehouseLocationService.update_location(db_session, loc.id, update, loc.version_id)
