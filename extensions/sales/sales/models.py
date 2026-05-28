import uuid
from datetime import date
from decimal import Decimal
from typing import Optional, List
from sqlmodel import Field, Relationship
from sqlalchemy import Column, Numeric

from core.models.base import BESBase


class SalesQuotation(BESBase, table=True):
    __tablename__ = "sales_quotations"

    ref_number: str = Field(index=True, unique=True)
    customer_id: uuid.UUID
    valid_until: date
    status: str = Field(default="draft")  # draft, active, won, lost, expired

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

    line_items: List["SalesQuotationLine"] = Relationship(
        back_populates="quotation",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class SalesQuotationLine(BESBase, table=True):
    __tablename__ = "sales_quotation_lines"

    quotation_id: uuid.UUID = Field(foreign_key="sales_quotations.id")
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

    quotation: SalesQuotation = Relationship(back_populates="line_items")


class SalesOrder(BESBase, table=True):
    __tablename__ = "sales_orders"

    ref_number: str = Field(index=True, unique=True)
    customer_id: uuid.UUID
    quotation_id: Optional[uuid.UUID] = Field(default=None)  # Ghost FK to sales_quotations
    payment_terms: str
    status: str = Field(default="draft")  # draft, confirmed, partially_shipped, shipped, partially_invoiced, invoiced, completed, cancelled
    credit_warning: bool = Field(default=False)
    cloned_from_id: Optional[uuid.UUID] = Field(default=None)

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

    line_items: List["SalesOrderLine"] = Relationship(
        back_populates="order",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class SalesOrderLine(BESBase, table=True):
    __tablename__ = "sales_order_lines"

    order_id: uuid.UUID = Field(foreign_key="sales_orders.id")
    product_id: uuid.UUID  # Ghost FK to core.products
    qty: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    shipped_qty: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    invoiced_qty: Decimal = Field(
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

    order: SalesOrder = Relationship(back_populates="line_items")
