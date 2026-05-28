import uuid
from decimal import Decimal
from typing import Optional
from sqlmodel import Field
from sqlalchemy import Column, Numeric

from .base import BESBase


class Customer(BESBase, table=True):
    __tablename__ = "customers"
    name: str
    tax_id: Optional[str] = None
    primary_email: Optional[str] = None
    credit_limit: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    outstanding_balance: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )


class Vendor(BESBase, table=True):
    __tablename__ = "vendors"
    name: str
    tax_id: Optional[str] = None
    primary_email: Optional[str] = None
    payment_terms: Optional[str] = None  # e.g., "Net 30"


class Product(BESBase, table=True):
    __tablename__ = "products"
    name: str
    sku: str = Field(index=True, unique=True)
    # Enforced Decimal(20,4) per ARCHITECTURE.md §7.A "Money Rule"
    base_price: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    uom_id: Optional[uuid.UUID] = Field(default=None, foreign_key="uoms.id")


class UOM(BESBase, table=True):
    __tablename__ = "uoms"
    code: str = Field(index=True, unique=True)  # e.g., 'KG', 'EA'
    name: str  # e.g., 'Kilograms', 'Each'
    description: Optional[str] = None
