import uuid
from datetime import datetime
from typing import Optional
from decimal import Decimal
from sqlmodel import Field
from sqlalchemy import Column, Numeric
from core.models import BESBase

class InventoryEntity(BESBase, table=True):
    __tablename__ = "inventory_entities"
    
    name: str = Field(index=True)
    description: str = Field(default="")


class InventoryItemDetails(BESBase, table=True):
    """
    Extends core.Product with inventory-specific configurations.
    Enforces the 'Money Rule' using Numeric(20,4) for standard and average costing.
    """
    __tablename__ = "inventory_item_details"

    product_id: uuid.UUID = Field(
        foreign_key="products.id",
        unique=True,
        nullable=False,
        index=True
    )
    costing_method: str = Field(default="STANDARD", nullable=False) # STANDARD, FIFO, WAC
    
    # Financial quantities and pricing
    standard_cost: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4), nullable=False)
    )
    weighted_average_cost: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4), nullable=False)
    )
    
    # Stock alert and replenishment thresholds
    safety_stock: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4), nullable=False)
    )
    reorder_point: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4), nullable=False)
    )
    
    # Tracking options
    is_serial_tracked: bool = Field(default=False, nullable=False)
    is_lot_tracked: bool = Field(default=False, nullable=False)
    
    notes: Optional[str] = Field(default=None, nullable=True)


class InventoryUomConversion(BESBase, table=True):
    """
    Multi-UOM Conversion registry.
    Calculates scale factors to standardise transactions in Base UOMs.
    """
    __tablename__ = "inventory_uom_conversions"

    product_id: uuid.UUID = Field(
        foreign_key="products.id",
        nullable=False,
        index=True
    )
    from_uom_id: uuid.UUID = Field(
        foreign_key="uoms.id",
        nullable=False
    )
    to_uom_id: uuid.UUID = Field(
        foreign_key="uoms.id",
        nullable=False
    )
    
    # High-precision multiplier to avoid rounding errors during stock conversions
    multiplier: Decimal = Field(
        sa_column=Column(Numeric(precision=20, scale=8), nullable=False)
    )


class InventoryLot(BESBase, table=True):
    """
    Lot master registry for traceable batches (pharma, batch materials).
    """
    __tablename__ = "inventory_lots"

    product_id: uuid.UUID = Field(
        foreign_key="products.id",
        nullable=False,
        index=True
    )
    lot_number: str = Field(index=True, nullable=False)
    manufacturing_date: Optional[datetime] = Field(default=None, nullable=True)
    expiry_date: Optional[datetime] = Field(default=None, nullable=True)
    is_active: bool = Field(default=True, nullable=False)


class InventoryWarehouseLocation(BESBase, table=True):
    """
    Registry of physical warehouses, stores, zones, and bins.
    Integrates with multi-tenant subsidiary constraints.
    """
    __tablename__ = "inventory_warehouse_locations"

    code: str = Field(index=True, unique=True, nullable=False)
    name: str = Field(nullable=False)
    type: str = Field(default="WAREHOUSE", nullable=False) # WAREHOUSE, ZONE, BIN, SHOWROOM, QUALITY_GATE
    parent_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="inventory_warehouse_locations.id",
        nullable=True
    )
    address: Optional[str] = Field(default=None, nullable=True)
    contact_name: Optional[str] = Field(default=None, nullable=True)
    contact_phone: Optional[str] = Field(default=None, nullable=True)
    
    # Capacity measurements
    max_volume: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4), nullable=False)
    )
    max_weight: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4), nullable=False)
    )
    
    is_active: bool = Field(default=True, nullable=False)
    audit_locked: bool = Field(default=False, nullable=False)
    restricted_item_categories: Optional[str] = Field(default=None, nullable=True)
