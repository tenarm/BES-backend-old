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

class SalesCustomerDetails(BESBase, table=True):
    __tablename__ = "sales_customer_details"
    
    customer_id: uuid.UUID = Field(foreign_key="customers.id", unique=True, index=True)
    credit_limit: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    payment_terms: str = Field(default="Net 30")
    currency: str = Field(default="USD")
    credit_hold: bool = Field(default=False)
    notes: Optional[str] = Field(default=None)

class SalesCustomerAddress(BESBase, table=True):
    __tablename__ = "sales_customer_addresses"
    
    customer_id: uuid.UUID = Field(foreign_key="customers.id", index=True)
    address_type: str = Field(default="BILLING")  # BILLING, SHIPPING
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: Optional[str] = None
    postal_code: str
    country: str
    is_primary: bool = Field(default=False)

class SalesCustomerContact(BESBase, table=True):
    __tablename__ = "sales_customer_contacts"
    
    customer_id: uuid.UUID = Field(foreign_key="customers.id", index=True)
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str = Field(default="BILLING")  # BILLING, PURCHASING, LOGISTICS
