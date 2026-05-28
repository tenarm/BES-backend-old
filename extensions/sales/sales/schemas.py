import uuid
from datetime import date
from decimal import Decimal
from typing import Optional, List
from sqlmodel import SQLModel


class SalesQuotationLineCreate(SQLModel):
    product_id: uuid.UUID
    qty: Decimal
    unit_price: Decimal
    discount_amount: Decimal = Decimal("0.0")
    tax_rate: Decimal = Decimal("0.0")


class SalesQuotationLineRead(SQLModel):
    id: uuid.UUID
    product_id: uuid.UUID
    qty: Decimal
    unit_price: Decimal
    discount_amount: Decimal
    tax_rate: Decimal
    line_total: Decimal


class SalesQuotationCreate(SQLModel):
    customer_id: uuid.UUID
    valid_until: date
    line_items: List[SalesQuotationLineCreate]


class SalesQuotationRead(SQLModel):
    id: uuid.UUID
    ref_number: str
    customer_id: uuid.UUID
    valid_until: date
    status: str
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    line_items: List[SalesQuotationLineRead]
    version_id: int


class SalesOrderLineCreate(SQLModel):
    product_id: uuid.UUID
    qty: Decimal
    unit_price: Decimal
    discount_amount: Decimal = Decimal("0.0")
    tax_rate: Decimal = Decimal("0.0")


class SalesOrderLineRead(SQLModel):
    id: uuid.UUID
    product_id: uuid.UUID
    qty: Decimal
    shipped_qty: Decimal
    invoiced_qty: Decimal
    unit_price: Decimal
    discount_amount: Decimal
    tax_rate: Decimal
    line_total: Decimal


class SalesOrderCreate(SQLModel):
    customer_id: uuid.UUID
    payment_terms: str
    quotation_id: Optional[uuid.UUID] = None
    line_items: List[SalesOrderLineCreate]


class SalesOrderRead(SQLModel):
    id: uuid.UUID
    ref_number: str
    customer_id: uuid.UUID
    quotation_id: Optional[uuid.UUID]
    payment_terms: str
    status: str
    credit_warning: bool
    cloned_from_id: Optional[uuid.UUID]
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    line_items: List[SalesOrderLineRead]
    version_id: int
