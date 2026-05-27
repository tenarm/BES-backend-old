import uuid
from typing import Optional, List
from decimal import Decimal
from datetime import date
from sqlmodel import SQLModel

class SupplyChainEntityCreate(SQLModel):
    name: str
    description: str = ""

class SupplyChainEntityRead(SQLModel):
    id: uuid.UUID
    name: str
    description: str


class SupplierAddressCreate(SQLModel):
    address_type: str = "BILLING_REMIT"  # BILLING_REMIT, SHIP_FROM
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: Optional[str] = None
    postal_code: str
    country: str
    is_primary: bool = False

class SupplierAddressRead(SQLModel):
    id: uuid.UUID
    vendor_id: uuid.UUID
    address_type: str
    address_line1: str
    address_line2: Optional[str]
    city: str
    state: Optional[str]
    postal_code: str
    country: str
    is_primary: bool


class SupplierContactCreate(SQLModel):
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str = "SOURCING"  # SOURCING, FINANCE, LOGISTICS
    is_primary: bool = False

class SupplierContactRead(SQLModel):
    id: uuid.UUID
    vendor_id: uuid.UUID
    full_name: str
    email: Optional[str]
    phone: Optional[str]
    role: str
    is_primary: bool


class SupplierDetailsCreate(SQLModel):
    currency: str = "USD"
    lead_time_days: int = 7
    otif_target: Decimal = Decimal("95.0000")
    notes: Optional[str] = None

class SupplierDetailsUpdate(SQLModel):
    currency: Optional[str] = None
    lead_time_days: Optional[int] = None
    otif_target: Optional[Decimal] = None
    purchasing_hold: Optional[bool] = None
    payment_hold: Optional[bool] = None
    notes: Optional[str] = None

class SupplierDetailsRead(SQLModel):
    id: uuid.UUID
    vendor_id: uuid.UUID
    currency: str
    lead_time_days: int
    otif_target: Decimal
    otif_score: Decimal
    defect_rate: Decimal
    purchasing_hold: bool
    payment_hold: bool
    notes: Optional[str]


class SupplierCertificationCreate(SQLModel):
    cert_type: str
    cert_number: str
    issuing_authority: str
    issue_date: date
    expiry_date: date

class SupplierCertificationRead(SQLModel):
    id: uuid.UUID
    vendor_id: uuid.UUID
    cert_type: str
    cert_number: str
    issuing_authority: str
    issue_date: date
    expiry_date: date
    is_active: bool


class SupplierOnboard(SQLModel):
    name: str
    tax_id: Optional[str] = None
    primary_email: Optional[str] = None
    payment_terms: Optional[str] = "Net 30"  # Writes to core.vendors
    currency: str = "USD"
    lead_time_days: int = 7
    otif_target: Decimal = Decimal("95.0000")
    notes: Optional[str] = None
    addresses: List[SupplierAddressCreate] = []
    contacts: List[SupplierContactCreate] = []

class SupplierUpdate(SQLModel):
    name: Optional[str] = None
    tax_id: Optional[str] = None
    primary_email: Optional[str] = None
    payment_terms: Optional[str] = None
    currency: Optional[str] = None
    lead_time_days: Optional[int] = None
    otif_target: Optional[Decimal] = None
    purchasing_hold: Optional[bool] = None
    payment_hold: Optional[bool] = None
    notes: Optional[str] = None
    addresses: Optional[List[SupplierAddressCreate]] = None
    contacts: Optional[List[SupplierContactCreate]] = None

class SupplierRead(SQLModel):
    id: uuid.UUID  # Base Vendor ID
    name: str
    tax_id: Optional[str]
    primary_email: Optional[str]
    payment_terms: Optional[str]
    version_id: int  # Concurrency optimistic locking
    currency: str
    lead_time_days: int
    otif_target: Decimal
    otif_score: Decimal
    defect_rate: Decimal
    purchasing_hold: bool
    payment_hold: bool
    notes: Optional[str]
    addresses: List[SupplierAddressRead] = []
    contacts: List[SupplierContactRead] = []
    certifications: List[SupplierCertificationRead] = []
