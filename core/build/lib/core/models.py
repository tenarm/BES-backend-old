import uuid
from datetime import datetime, timezone
from typing import Optional, Any
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class ERPBase(SQLModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    created_by: Optional[str] = Field(default=None)
    subsidiary_id: Optional[str] = Field(default=None, index=True)
    is_deleted: bool = Field(default=False)
    # Using JSON for sqlite compatibility
    metadata_: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)

class Customer(ERPBase, table=True):
    __tablename__ = "customers"
    name: str
    tax_id: Optional[str] = None
    primary_email: Optional[str] = None

class Product(ERPBase, table=True):
    __tablename__ = "products"
    name: str
    sku: str = Field(index=True, unique=True)
    base_price: float = Field(default=0.0)
