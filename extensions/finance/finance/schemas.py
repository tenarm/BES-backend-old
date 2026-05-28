import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List
from sqlmodel import SQLModel


class FinanceInvoiceLineCreate(SQLModel):
    product_id: uuid.UUID
    qty: Decimal
    unit_price: Decimal
    discount_amount: Decimal = Decimal("0.0")
    tax_rate: Decimal = Decimal("0.0")


class FinanceInvoiceLineRead(SQLModel):
    id: uuid.UUID
    product_id: uuid.UUID
    qty: Decimal
    unit_price: Decimal
    discount_amount: Decimal
    tax_rate: Decimal
    line_total: Decimal


class FinanceInvoiceCreate(SQLModel):
    order_id: uuid.UUID
    customer_id: uuid.UUID
    due_date: date
    line_items: List[FinanceInvoiceLineCreate]


class FinanceInvoiceRead(SQLModel):
    id: uuid.UUID
    ref_number: str
    order_id: uuid.UUID
    customer_id: uuid.UUID
    due_date: date
    status: str
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    balance_due: Decimal
    line_items: List[FinanceInvoiceLineRead]
    version_id: int


class FinancePaymentCreate(SQLModel):
    invoice_id: uuid.UUID
    amount: Decimal
    payment_method: str


class FinancePaymentRead(SQLModel):
    id: uuid.UUID
    ref_number: str
    invoice_id: uuid.UUID
    amount: Decimal
    payment_method: str
    payment_date: datetime
    status: str
    version_id: int
