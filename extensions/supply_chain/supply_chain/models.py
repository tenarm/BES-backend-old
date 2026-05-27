import uuid
from typing import Optional
from decimal import Decimal
from datetime import date
from sqlmodel import Field
from sqlalchemy import Column, Numeric
from core.models import BESBase

class SupplyChainEntity(BESBase, table=True):
    __tablename__ = "supply_chain_entities"
    
    name: str = Field(index=True)
    description: str = Field(default="")


class SupplierDetails(BESBase, table=True):
    """
    SupplierDetails extends the core Vendor model in a hub-and-spoke MDM pattern.
    Stores supply-chain-specific configurations, hold states, and rolling performance ratings.
    """
    __tablename__ = "supply_chain_supplier_details"

    vendor_id: uuid.UUID = Field(foreign_key="vendors.id", unique=True, index=True)
    currency: str = Field(default="USD")
    lead_time_days: int = Field(default=7)
    otif_target: Decimal = Field(
        default=Decimal("95.0000"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    otif_score: Decimal = Field(
        default=Decimal("100.0000"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    defect_rate: Decimal = Field(
        default=Decimal("0.0000"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    purchasing_hold: bool = Field(default=False)
    payment_hold: bool = Field(default=False)
    notes: Optional[str] = Field(default=None)


class SupplierAddress(BESBase, table=True):
    """
    SupplierAddress stores multiple addresses associated with a vendor (e.g., Billing, Shipping).
    """
    __tablename__ = "supply_chain_supplier_addresses"

    vendor_id: uuid.UUID = Field(foreign_key="vendors.id", index=True)
    address_type: str = Field(default="BILLING_REMIT")  # e.g., BILLING_REMIT, SHIP_FROM
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: Optional[str] = None
    postal_code: str
    country: str  # ISO 2-character country code
    is_primary: bool = Field(default=False)


class SupplierContact(BESBase, table=True):
    """
    SupplierContact stores multiple contact persons under a vendor's organization.
    """
    __tablename__ = "supply_chain_supplier_contacts"

    vendor_id: uuid.UUID = Field(foreign_key="vendors.id", index=True)
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str = Field(default="SOURCING")  # e.g., SOURCING, FINANCE, LOGISTICS
    is_primary: bool = Field(default=False)


class SupplierCertification(BESBase, table=True):
    """
    SupplierCertification tracks vendor compliance document audits (e.g., ISO-9001).
    """
    __tablename__ = "supply_chain_supplier_certifications"

    vendor_id: uuid.UUID = Field(foreign_key="vendors.id", index=True)
    cert_type: str  # e.g., ISO_9001, ISO_14001, LIABILITY_INSURANCE
    cert_number: str
    issuing_authority: str
    issue_date: date
    expiry_date: date
    is_active: bool = Field(default=True)
