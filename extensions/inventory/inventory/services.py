import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.repository import BaseRepository
from core.sequences import SequenceService
from core.events import event_bus, BaseEventPayload
from core.exceptions import EntityNotFoundError, StateTransitionError
from .models import InventoryShipment, InventoryShipmentLine
from .schemas import InventoryShipmentCreate


class ShipmentRepository(BaseRepository[InventoryShipment]):
    def __init__(self):
        super().__init__(InventoryShipment)


shipment_repo = ShipmentRepository()


class ShipmentService:
    def __init__(self):
        self.sequence_service = SequenceService()

    async def get_shipment(self, session: AsyncSession, shipment_id: uuid.UUID) -> Optional[InventoryShipment]:
        from sqlalchemy.orm import selectinload
        stmt = (
            select(InventoryShipment)
            .where(InventoryShipment.id == shipment_id)
            .options(selectinload(InventoryShipment.line_items))
        )
        res = await session.execute(stmt)
        return res.scalars().first()

    async def get_all_shipments(self, session: AsyncSession, skip: int = 0, limit: int = 100) -> Sequence[InventoryShipment]:
        from sqlalchemy.orm import selectinload
        stmt = (
            select(InventoryShipment)
            .options(selectinload(InventoryShipment.line_items))
            .offset(skip)
            .limit(limit)
        )
        res = await session.execute(stmt)
        return res.scalars().all()

    async def create_shipment(self, session: AsyncSession, obj_in: InventoryShipmentCreate) -> InventoryShipment:
        ref = await self.sequence_service.next_number(session, "inventory_shipment")

        line_items = []
        for line in obj_in.line_items:
            db_line = InventoryShipmentLine(
                product_id=line.product_id,
                qty=Decimal(str(line.qty))
            )
            line_items.append(db_line)

        from datetime import timezone
        shipment = InventoryShipment(
            ref_number=ref,
            order_id=obj_in.order_id,
            shipped_date=datetime.now(timezone.utc),
            status="draft",
            line_items=line_items
        )

        shipment = await shipment_repo.create(session, shipment)
        await session.commit()

        # Eagerly reload to attach loaded line items
        from sqlalchemy.orm import selectinload
        stmt = (
            select(InventoryShipment)
            .where(InventoryShipment.id == shipment.id)
            .options(selectinload(InventoryShipment.line_items))
        )
        res = await session.execute(stmt)
        return res.scalars().first()

    async def dispatch_shipment(self, session: AsyncSession, shipment_id: uuid.UUID) -> InventoryShipment:
        from sqlalchemy.orm import selectinload
        stmt = (
            select(InventoryShipment)
            .where(InventoryShipment.id == shipment_id)
            .options(selectinload(InventoryShipment.line_items))
            .with_for_update()
        )
        res = await session.execute(stmt)
        shipment = res.scalars().first()
        if not shipment:
            raise EntityNotFoundError("InventoryShipment", str(shipment_id))

        if shipment.status != "draft":
            raise StateTransitionError("InventoryShipment", shipment.status, "shipped")

        from datetime import timezone
        shipment.status = "shipped"
        shipment.shipped_date = datetime.now(timezone.utc)
        session.add(shipment)

        event_payload = BaseEventPayload(
            emitter_module="inventory",
            event_type="SELL_ORDER_SHIPPED",
            data={
                "shipment_id": str(shipment.id),
                "order_id": str(shipment.order_id),
                "shipped_items": [
                    {
                        "product_id": str(line.product_id),
                        "qty": str(line.qty)
                    }
                    for line in shipment.line_items
                ]
            }
        )

        await session.commit()
        await event_bus.emit(event_payload)
        return shipment
