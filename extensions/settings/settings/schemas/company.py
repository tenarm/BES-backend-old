import uuid
from typing import Optional
from decimal import Decimal
from sqlmodel import SQLModel

class CompanyProfileCreate(SQLModel):
    legal_name: str
    dba_name: Optional[str] = None
    tax_identifier: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    default_language: str = "en"
    logo_url: Optional[str] = None

class CompanyProfileRead(SQLModel):
    id: uuid.UUID
    legal_name: str
    dba_name: Optional[str]
    tax_identifier: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    website: Optional[str]
    default_language: str
    logo_url: Optional[str]
    version_id: int

class CompanyProfileUpdate(SQLModel):
    legal_name: Optional[str] = None
    dba_name: Optional[str] = None
    tax_identifier: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    default_language: Optional[str] = None
    logo_url: Optional[str] = None

class SubsidiaryCreate(SQLModel):
    name: str
    parent_id: Optional[uuid.UUID] = None
    base_currency: str = "USD"
    tax_identifier: Optional[str] = None
    address_billing: str = ""
    address_shipping: str = ""
    is_active: bool = True

class SubsidiaryRead(SQLModel):
    id: uuid.UUID
    name: str
    parent_id: Optional[uuid.UUID]
    base_currency: str
    tax_identifier: Optional[str]
    address_billing: str
    address_shipping: str
    is_active: bool
    version_id: int

class SubsidiaryUpdate(SQLModel):
    name: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None
    base_currency: Optional[str] = None
    tax_identifier: Optional[str] = None
    address_billing: Optional[str] = None
    address_shipping: Optional[str] = None
    is_active: Optional[bool] = None

class FiscalCalendarCreate(SQLModel):
    name: str
    start_date: str
    end_date: str
    status: str = "OPEN"

class FiscalCalendarRead(SQLModel):
    id: uuid.UUID
    name: str
    start_date: str
    end_date: str
    status: str
    version_id: int

class FiscalCalendarUpdate(SQLModel):
    name: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[str] = None

class PostingPeriodCreate(SQLModel):
    calendar_id: uuid.UUID
    name: str
    start_date: str
    end_date: str
    is_locked: bool = False

class PostingPeriodRead(SQLModel):
    id: uuid.UUID
    calendar_id: uuid.UUID
    name: str
    start_date: str
    end_date: str
    is_locked: bool
    version_id: int

class PostingPeriodUpdate(SQLModel):
    is_locked: Optional[bool] = None

class TaxProfileCreate(SQLModel):
    name: str
    jurisdiction: str
    tax_rate: Decimal
    is_active: bool = True

class TaxProfileRead(SQLModel):
    id: uuid.UUID
    name: str
    jurisdiction: str
    tax_rate: Decimal
    is_active: bool
    version_id: int

class TaxProfileUpdate(SQLModel):
    name: Optional[str] = None
    jurisdiction: Optional[str] = None
    tax_rate: Optional[Decimal] = None
    is_active: Optional[bool] = None
