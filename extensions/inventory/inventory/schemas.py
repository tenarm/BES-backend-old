import uuid
from datetime import datetime
from decimal import Decimal
from typing import List
from sqlmodel import SQLModel


class InventoryShipmentLineCreate(SQLModel):
    product_id: uuid.UUID
    qty: Decimal


class InventoryShipmentLineRead(SQLModel):
    id: uuid.UUID
    product_id: uuid.UUID
    qty: Decimal


class InventoryShipmentCreate(SQLModel):
    order_id: uuid.UUID
    line_items: List[InventoryShipmentLineCreate]


class InventoryShipmentRead(SQLModel):
    id: uuid.UUID
    ref_number: str
    order_id: uuid.UUID
    shipped_date: datetime
    status: str
    line_items: List[InventoryShipmentLineRead]
    version_id: int
