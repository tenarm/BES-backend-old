import uuid
from decimal import Decimal
from enum import Enum
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Numeric
from core.models import BESBase, Customer, Product

class QuotationStatus(str, Enum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

class SalesCustomerDetails(BESBase, table=True):
    __tablename__ = "sales_customer_details"
    customer_id: uuid.UUID = Field(foreign_key="customers.id", unique=True)
    credit_limit: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    discount_tier: int = Field(default=1)

class Quotation(BESBase, table=True):
    __tablename__ = "sales_quotations"
    customer_id: uuid.UUID = Field(foreign_key="customers.id")
    posting_date: Optional[str] = None
    valid_until: Optional[str] = None
    status: QuotationStatus = Field(default=QuotationStatus.DRAFT)
    total_amount: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    
    # Relationships
    items: List["QuotationItem"] = Relationship(back_populates="quotation")

class QuotationItem(BESBase, table=True):
    __tablename__ = "sales_quotation_items"
    quotation_id: uuid.UUID = Field(foreign_key="sales_quotations.id")
    product_id: uuid.UUID = Field(foreign_key="products.id")
    qty: Decimal = Field(
        default=Decimal("1.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    rate: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    amount: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )

    # Relationships
    quotation: Quotation = Relationship(back_populates="items")

class SalesOrder(BESBase, table=True):
    __tablename__ = "sales_orders"
    customer_id: uuid.UUID = Field(foreign_key="customers.id")
    total_amount: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    status: str = Field(default="DRAFT")
    quotation_id: Optional[uuid.UUID] = Field(default=None, foreign_key="sales_quotations.id")

