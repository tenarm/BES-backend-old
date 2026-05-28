import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from sqlmodel import Field, Relationship
from sqlalchemy import Column, Numeric

from core.models.base import BESBase


class FinanceInvoice(BESBase, table=True):
    __tablename__ = "finance_invoices"

    ref_number: str = Field(index=True, unique=True)
    order_id: uuid.UUID  # Ghost FK to sales_orders
    customer_id: uuid.UUID  # Ghost FK to core.customers
    due_date: date
    status: str = Field(default="draft")  # draft, issued, partially_paid, paid, cancelled

    subtotal: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    tax_amount: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    total_amount: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    balance_due: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )

    line_items: List["FinanceInvoiceLine"] = Relationship(
        back_populates="invoice",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class FinanceInvoiceLine(BESBase, table=True):
    __tablename__ = "finance_invoice_lines"

    invoice_id: uuid.UUID = Field(foreign_key="finance_invoices.id")
    product_id: uuid.UUID  # Ghost FK to core.products
    qty: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    unit_price: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    discount_amount: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    tax_rate: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    line_total: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )

    invoice: FinanceInvoice = Relationship(back_populates="line_items")


class FinancePayment(BESBase, table=True):
    __tablename__ = "finance_payments"

    ref_number: str = Field(index=True, unique=True)
    invoice_id: uuid.UUID  # Ghost FK to finance_invoices
    amount: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    payment_method: str  # cash, bank_transfer, credit_card
    payment_date: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="pending")  # pending, completed, failed
