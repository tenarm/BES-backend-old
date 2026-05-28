import uuid
from datetime import datetime
from decimal import Decimal
from typing import List
from sqlmodel import Field, Relationship
from sqlalchemy import Column, Numeric

from core.models.base import BESBase


class InventoryShipment(BESBase, table=True):
    __tablename__ = "inventory_shipments"

    ref_number: str = Field(index=True, unique=True)
    order_id: uuid.UUID  # Ghost FK to sales_orders
    shipped_date: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="draft")  # draft, packed, shipped, delivered

    line_items: List["InventoryShipmentLine"] = Relationship(
        back_populates="shipment",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class InventoryShipmentLine(BESBase, table=True):
    __tablename__ = "inventory_shipment_lines"

    shipment_id: uuid.UUID = Field(foreign_key="inventory_shipments.id")
    product_id: uuid.UUID  # Ghost FK to core.products
    qty: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )

    shipment: InventoryShipment = Relationship(back_populates="line_items")
