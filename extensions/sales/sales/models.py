import uuid
from typing import Optional
from decimal import Decimal
from sqlmodel import Field
from sqlalchemy import Column, Numeric
from core.models import BESBase

class SalesEntity(BESBase, table=True):
    __tablename__ = "sales_entities"
    
    name: str = Field(index=True)
    description: str = Field(default="")

class CustomerAddress(BESBase, table=True):
    __tablename__ = "customer_addresses"

    customer_id: uuid.UUID = Field(foreign_key="customers.id", index=True)
    address_type: str = Field(index=True)  # BILLING, SHIPPING
    street_address: str = Field(max_length=512)
    city: str = Field(max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=20)
    country_code: str = Field(max_length=2)
    is_default: bool = Field(default=False)

class CustomerContact(BESBase, table=True):
    __tablename__ = "customer_contacts"

    customer_id: uuid.UUID = Field(foreign_key="customers.id", index=True)
    first_name: str = Field(max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    department: Optional[str] = Field(default=None, max_length=100)  # e.g., 'Finance', 'Logistics'

class CustomerCredit(BESBase, table=True):
    __tablename__ = "customer_credits"

    customer_id: uuid.UUID = Field(foreign_key="customers.id", unique=True, index=True)
    credit_limit: Decimal = Field(
        default=Decimal("0.0000"),
        sa_column=Column(Numeric(precision=20, scale=4), nullable=False, server_default="0.0000")
    )
    outstanding_balance: Decimal = Field(
        default=Decimal("0.0000"),
        sa_column=Column(Numeric(precision=20, scale=4), nullable=False, server_default="0.0000")
    )
    payment_terms_code: Optional[str] = Field(default=None, max_length=50)
    status: str = Field(default="ACTIVE")  # ACTIVE, CREDIT_HOLD
