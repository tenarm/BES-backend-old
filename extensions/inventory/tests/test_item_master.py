import pytest
import uuid
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.models import UOM, Product
from inventory.models import InventoryItemDetails, InventoryUomConversion, InventoryLot
from inventory.services import ItemMasterService, InventoryLotService, CircularUomConversionError, DuplicateSkuError, ConcurrencyError


@pytest.mark.asyncio
async def test_onboard_item_success(db_session: AsyncSession):
    # 1. Seed a Base UOM
    base_uom = UOM(code="EA", name="Each", description="Base Unit")
    db_session.add(base_uom)
    await db_session.commit()
    await db_session.refresh(base_uom)

    # 2. Onboard Item using service
    from inventory.schemas import ItemDetailsCreate
    data = ItemDetailsCreate(
        name="Test Component",
        sku="TEST-COMP-001",
        base_price=Decimal("49.9900"),
        uom_id=base_uom.id,
        costing_method="WAC",
        standard_cost=Decimal("20.0000"),
        weighted_average_cost=Decimal("20.0000"),
        safety_stock=Decimal("10.0000"),
        reorder_point=Decimal("5.0000")
    )
    
    result = await ItemMasterService.onboard_item(db_session, data)
    
    # 3. Assertions
    assert result["sku"] == "TEST-COMP-001"
    assert result["costing_method"] == "WAC"
    assert result["base_price"] == Decimal("49.9900")
    assert result["standard_cost"] == Decimal("20.0000")
    assert isinstance(result["standard_cost"], Decimal) # Money Rule check
    
    # Assert DB persistence
    prod_stmt = select(Product).where(Product.sku == "TEST-COMP-001")
    prod = (await db_session.execute(prod_stmt)).scalar()
    assert prod is not None
    assert prod.name == "Test Component"
    
    details_stmt = select(InventoryItemDetails).where(InventoryItemDetails.product_id == prod.id)
    details = (await db_session.execute(details_stmt)).scalar()
    assert details is not None
    assert details.costing_method == "WAC"


@pytest.mark.asyncio
async def test_prevent_duplicate_sku(db_session: AsyncSession):
    # Seed UOM
    base_uom = UOM(code="KG", name="Kilogram", description="Base Unit")
    db_session.add(base_uom)
    await db_session.commit()
    await db_session.refresh(base_uom)

    from inventory.schemas import ItemDetailsCreate
    data1 = ItemDetailsCreate(
        name="Material A",
        sku="MAT-A",
        base_price=Decimal("10.0"),
        uom_id=base_uom.id
    )
    await ItemMasterService.onboard_item(db_session, data1)

    # Try creating item with same SKU
    data2 = ItemDetailsCreate(
        name="Material B",
        sku="MAT-A",
        base_price=Decimal("15.0"),
        uom_id=base_uom.id
    )
    with pytest.raises(DuplicateSkuError):
        await ItemMasterService.onboard_item(db_session, data2)


@pytest.mark.asyncio
async def test_circular_uom_conversion_prevention(db_session: AsyncSession):
    # Seed UOMs
    uom_ea = UOM(code="EA_1", name="Each", description="Base Unit")
    uom_box = UOM(code="BOX_1", name="Box", description="Box Unit")
    uom_plt = UOM(code="PLT_1", name="Pallet", description="Pallet Unit")
    db_session.add_all([uom_ea, uom_box, uom_plt])
    await db_session.commit()
    await db_session.refresh(uom_ea)
    await db_session.refresh(uom_box)
    await db_session.refresh(uom_plt)

    # Onboard Item
    from inventory.schemas import ItemDetailsCreate
    item_data = ItemDetailsCreate(
        name="Convertible Item",
        sku="CONV-001",
        base_price=Decimal("5.0"),
        uom_id=uom_ea.id
    )
    item = await ItemMasterService.onboard_item(db_session, item_data)
    product_id = item["id"]

    # 1. Add EA -> BOX
    from inventory.schemas import UomConversionCreate
    conv1 = UomConversionCreate(from_uom_id=uom_ea.id, to_uom_id=uom_box.id, multiplier=Decimal("12.0"))
    await ItemMasterService.add_uom_conversion(db_session, product_id, conv1)

    # 2. Add BOX -> PLT
    conv2 = UomConversionCreate(from_uom_id=uom_box.id, to_uom_id=uom_plt.id, multiplier=Decimal("10.0"))
    await ItemMasterService.add_uom_conversion(db_session, product_id, conv2)

    # 3. Try adding PLT -> EA (Creates cycle PLT -> EA -> BOX -> PLT)
    conv3 = UomConversionCreate(from_uom_id=uom_plt.id, to_uom_id=uom_ea.id, multiplier=Decimal("0.00833333"))
    with pytest.raises(CircularUomConversionError):
        await ItemMasterService.add_uom_conversion(db_session, product_id, conv3)


@pytest.mark.asyncio
async def test_optimistic_concurrency_lock(db_session: AsyncSession):
    # Seed UOM & Item
    uom = UOM(code="MT", name="Meter", description="Base Unit")
    db_session.add(uom)
    await db_session.commit()
    await db_session.refresh(uom)

    from inventory.schemas import ItemDetailsCreate, ItemDetailsUpdate
    item_data = ItemDetailsCreate(
        name="Cable Wire",
        sku="WIRE-001",
        base_price=Decimal("1.50"),
        uom_id=uom.id
    )
    item = await ItemMasterService.onboard_item(db_session, item_data)
    product_id = item["id"]
    version_id = item["version_id"]

    # First update succeeds
    update1 = ItemDetailsUpdate(name="Cable Wire (Thick)")
    res1 = await ItemMasterService.update_item(db_session, product_id, update1, version_id)
    assert res1["version_id"] == version_id + 1

    # Second update using stale version fails
    update2 = ItemDetailsUpdate(name="Cable Wire (Thin)")
    with pytest.raises(ConcurrencyError):
        await ItemMasterService.update_item(db_session, product_id, update2, version_id)


@pytest.mark.asyncio
async def test_recalculate_weighted_average_cost(db_session: AsyncSession):
    # Seed UOM & Item
    uom = UOM(code="Ltr", name="Liter", description="Base Unit")
    db_session.add(uom)
    await db_session.commit()
    await db_session.refresh(uom)

    from inventory.schemas import ItemDetailsCreate
    item_data = ItemDetailsCreate(
        name="Chemical Liquid",
        sku="CHEM-001",
        base_price=Decimal("100.00"),
        uom_id=uom.id,
        weighted_average_cost=Decimal("10.0000") # Original WAC
    )
    item = await ItemMasterService.onboard_item(db_session, item_data)
    product_id = item["id"]

    # Recalculate cost upon receiving:
    # Existing Stock: 10 units at $10.00 each
    # Received: 5 units at $16.00 each
    # Formula: ((10 * 10) + (5 * 16)) / 15 = (100 + 80) / 15 = 180 / 15 = 12.00
    new_cost = await ItemMasterService.recalculate_weighted_average_cost(
        session=db_session,
        product_id=product_id,
        received_qty=Decimal("5.0"),
        received_price=Decimal("16.0"),
        current_stock=Decimal("10.0")
    )
    
    assert new_cost == Decimal("12.0000")
    
    # Assert DB update
    stmt = select(InventoryItemDetails).where(InventoryItemDetails.product_id == product_id)
    details = (await db_session.execute(stmt)).scalar()
    assert details.weighted_average_cost == Decimal("12.0000")
