import uuid
from typing import Optional
from decimal import Decimal
from datetime import datetime
from sqlmodel import SQLModel

class InventoryEntityCreate(SQLModel):
    name: str
    description: str = ""

class InventoryEntityRead(SQLModel):
    id: uuid.UUID
    name: str
    description: str


# --- Item Master Schemas ---

class ItemDetailsCreate(SQLModel):
    # Core Product fields
    name: str
    sku: str
    base_price: Decimal = Decimal("0.0")
    uom_id: uuid.UUID
    subsidiary_id: Optional[str] = None
    
    # Inventory specific fields
    costing_method: str = "STANDARD" # STANDARD, FIFO, WAC
    standard_cost: Decimal = Decimal("0.0")
    weighted_average_cost: Decimal = Decimal("0.0")
    safety_stock: Decimal = Decimal("0.0")
    reorder_point: Decimal = Decimal("0.0")
    is_serial_tracked: bool = False
    is_lot_tracked: bool = False
    notes: Optional[str] = None


class ItemDetailsUpdate(SQLModel):
    name: Optional[str] = None
    base_price: Optional[Decimal] = None
    uom_id: Optional[uuid.UUID] = None
    subsidiary_id: Optional[str] = None
    
    # Costing (only allowed if method can change or standard cost changes)
    costing_method: Optional[str] = None
    standard_cost: Optional[Decimal] = None
    weighted_average_cost: Optional[Decimal] = None
    safety_stock: Optional[Decimal] = None
    reorder_point: Optional[Decimal] = None
    is_serial_tracked: Optional[bool] = None
    is_lot_tracked: Optional[bool] = None
    notes: Optional[str] = None


class ItemDetailsRead(SQLModel):
    id: uuid.UUID # ID of the core.Product
    product_id: uuid.UUID # ID of the core.Product (linked 1:1)
    name: str
    sku: str
    base_price: Decimal
    uom_id: uuid.UUID
    subsidiary_id: Optional[str]
    is_deleted: bool
    version_id: int
    created_at: datetime
    updated_at: datetime

    costing_method: str
    standard_cost: Decimal
    weighted_average_cost: Decimal
    safety_stock: Decimal
    reorder_point: Decimal
    is_serial_tracked: bool
    is_lot_tracked: bool
    notes: Optional[str]


# --- UOM Conversion Schemas ---

class UomConversionCreate(SQLModel):
    from_uom_id: uuid.UUID
    to_uom_id: uuid.UUID
    multiplier: Decimal


class UomConversionRead(SQLModel):
    id: uuid.UUID
    product_id: uuid.UUID
    from_uom_id: uuid.UUID
    to_uom_id: uuid.UUID
    multiplier: Decimal
    created_at: datetime


# --- Lot Schemas ---

class LotCreate(SQLModel):
    lot_number: str
    manufacturing_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None


class LotRead(SQLModel):
    id: uuid.UUID
    product_id: uuid.UUID
    lot_number: str
    manufacturing_date: Optional[datetime]
    expiry_date: Optional[datetime]
    is_active: bool
    created_at: datetime


# --- Warehouse Location Schemas ---

class LocationCreate(SQLModel):
    code: str
    name: str
    type: str = "WAREHOUSE"
    parent_id: Optional[uuid.UUID] = None
    address: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    max_volume: Decimal = Decimal("0.0")
    max_weight: Decimal = Decimal("0.0")
    restricted_item_categories: Optional[str] = None


class LocationUpdate(SQLModel):
    name: Optional[str] = None
    type: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None
    address: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    max_volume: Optional[Decimal] = None
    max_weight: Optional[Decimal] = None
    is_active: Optional[bool] = None
    audit_locked: Optional[bool] = None
    restricted_item_categories: Optional[str] = None


class LocationRead(SQLModel):
    id: uuid.UUID
    code: str
    name: str
    type: str
    parent_id: Optional[uuid.UUID]
    address: Optional[str]
    contact_name: Optional[str]
    contact_phone: Optional[str]
    max_volume: Decimal
    max_weight: Decimal
    is_active: bool
    audit_locked: bool
    restricted_item_categories: Optional[str]
    subsidiary_id: Optional[str]
    version_id: int
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
