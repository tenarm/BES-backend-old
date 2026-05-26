import uuid
from typing import Optional, List
from decimal import Decimal
from sqlmodel import SQLModel

class SalesEntityCreate(SQLModel):
    name: str
    description: str = ""

class SalesEntityRead(SQLModel):
    id: uuid.UUID
    name: str
    description: str

class SalesCustomerAddressCreate(SQLModel):
    address_type: str = "BILLING"
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: Optional[str] = None
    postal_code: str
    country: str
    is_primary: bool = False

class SalesCustomerAddressRead(SQLModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    address_type: str
    address_line1: str
    address_line2: Optional[str]
    city: str
    state: Optional[str]
    postal_code: str
    country: str
    is_primary: bool

class SalesCustomerContactCreate(SQLModel):
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str = "BILLING"

class SalesCustomerContactRead(SQLModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    full_name: str
    email: Optional[str]
    phone: Optional[str]
    role: str

class SalesCustomerDetailsCreate(SQLModel):
    credit_limit: Decimal = Decimal("0.0")
    payment_terms: str = "Net 30"
    currency: str = "USD"
    notes: Optional[str] = None

class SalesCustomerDetailsUpdate(SQLModel):
    credit_limit: Optional[Decimal] = None
    payment_terms: Optional[str] = None
    currency: Optional[str] = None
    credit_hold: Optional[bool] = None
    notes: Optional[str] = None

class SalesCustomerDetailsRead(SQLModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    credit_limit: Decimal
    payment_terms: str
    currency: str
    credit_hold: bool
    notes: Optional[str]

class CustomerCommercialOnboard(SQLModel):
    name: str
    tax_id: Optional[str] = None
    primary_email: Optional[str] = None
    credit_limit: Decimal = Decimal("0.0")
    payment_terms: str = "Net 30"
    currency: str = "USD"
    notes: Optional[str] = None
    addresses: List[SalesCustomerAddressCreate] = []
    contacts: List[SalesCustomerContactCreate] = []

class CustomerCommercialUpdate(SQLModel):
    name: Optional[str] = None
    tax_id: Optional[str] = None
    primary_email: Optional[str] = None
    credit_limit: Optional[Decimal] = None
    payment_terms: Optional[str] = None
    currency: Optional[str] = None
    credit_hold: Optional[bool] = None
    notes: Optional[str] = None
    addresses: Optional[List[SalesCustomerAddressCreate]] = None
    contacts: Optional[List[SalesCustomerContactCreate]] = None

class CustomerCommercialRead(SQLModel):
    id: uuid.UUID
    name: str
    tax_id: Optional[str]
    primary_email: Optional[str]
    version_id: int
    credit_limit: Decimal
    payment_terms: str
    currency: str
    credit_hold: bool
    notes: Optional[str]
    addresses: List[SalesCustomerAddressRead] = []
    contacts: List[SalesCustomerContactRead] = []
