"""
Sales module API schemas.
Separate from ORM models to prevent users from injecting
internal fields like id, created_at, is_deleted, subsidiary_id.
"""
import uuid
from decimal import Decimal
from typing import Optional, List
from sqlmodel import SQLModel
from .models import QuotationStatus


# --- Customer Details Schemas ---
class SalesCustomerDetailsCreate(SQLModel):
    customer_id: uuid.UUID
    credit_limit: Decimal = Decimal("0.0")
    discount_tier: int = 1


# --- Quotation Schemas ---
class QuotationItemCreate(SQLModel):
    product_id: uuid.UUID
    qty: Decimal = Decimal("1.0")
    rate: Decimal = Decimal("0.0")

class QuotationItemRead(QuotationItemCreate):
    id: uuid.UUID
    amount: Decimal

class QuotationCreate(SQLModel):
    customer_id: uuid.UUID
    posting_date: Optional[str] = None
    valid_until: Optional[str] = None
    items: List[QuotationItemCreate] = []

class QuotationRead(SQLModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    posting_date: Optional[str] = None
    valid_until: Optional[str] = None
    status: QuotationStatus
    total_amount: Decimal
    items: List[QuotationItemRead] = []


# --- Sales Order Schemas ---
class SalesOrderCreate(SQLModel):
    customer_id: uuid.UUID
    total_amount: Decimal = Decimal("0.0")
    quotation_id: Optional[uuid.UUID] = None

class SalesOrderRead(SQLModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    total_amount: Decimal
    status: str
    quotation_id: Optional[uuid.UUID] = None
