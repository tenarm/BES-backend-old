import pytest
from decimal import Decimal
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.services import ShipmentService
from inventory.schemas import InventoryShipmentCreate, InventoryShipmentLineCreate


@pytest.mark.asyncio
async def test_shipment_lifecycle(db_session: AsyncSession):
    order_id = uuid.uuid4()
    product_id = uuid.uuid4()

    line = InventoryShipmentLineCreate(
        product_id=product_id,
        qty=Decimal("5.0")
    )
    shipment_in = InventoryShipmentCreate(
        order_id=order_id,
        line_items=[line]
    )

    service = ShipmentService()
    shipment = await service.create_shipment(db_session, shipment_in)

    assert shipment.status == "draft"
    assert shipment.ref_number.startswith("SH-")
    assert len(shipment.line_items) == 1
    assert shipment.line_items[0].qty == Decimal("5.0")

    dispatched = await service.dispatch_shipment(db_session, shipment.id)
    assert dispatched.status == "shipped"
