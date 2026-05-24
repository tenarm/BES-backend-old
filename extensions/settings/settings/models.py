import uuid
from datetime import date, datetime
from typing import Optional
from decimal import Decimal
from sqlmodel import Field, SQLModel
from sqlalchemy import Column, Numeric
from core.models import BESBase

class SettingsEntity(BESBase, table=True):
    __tablename__ = "settings_entities"
    
    name: str = Field(index=True)
    description: str = Field(default="")

class CompanyProfile(BESBase, table=True):
    __tablename__ = "company_profiles"
    
    name: str = Field(index=True)
    legal_name: str
    registration_id: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    logo_light_url: Optional[str] = None
    logo_dark_url: Optional[str] = None
    primary_brand_color: Optional[str] = None
    timezone: str = Field(default="UTC")
    base_currency: str = Field(default="USD")
    date_format: str = Field(default="YYYY-MM-DD")
    number_format: str = Field(default="1,000.00")

class Subsidiary(BESBase, table=True):
    __tablename__ = "subsidiaries"
    
    name: str = Field(index=True, unique=True)
    legal_name: str
    tax_id: Optional[str] = None
    parent_id: Optional[uuid.UUID] = Field(default=None, foreign_key="subsidiaries.id")
    country_code: str
    currency_code: str
    status: str = Field(default="ACTIVE")  # ACTIVE, INACTIVE

class FiscalYear(BESBase, table=True):
    __tablename__ = "fiscal_years"
    
    name: str = Field(index=True)
    start_date: date
    end_date: date
    status: str = Field(default="ACTIVE")  # ACTIVE, CLOSED

class PostingPeriod(BESBase, table=True):
    __tablename__ = "posting_periods"
    
    fiscal_year_id: uuid.UUID = Field(foreign_key="fiscal_years.id")
    name: str = Field(index=True)
    start_date: date
    end_date: date
    status: str = Field(default="OPEN")  # OPEN, LOCKED, CLOSING
    locked_at: Optional[datetime] = None
    locked_by: Optional[uuid.UUID] = None

class TaxProfile(BESBase, table=True):
    __tablename__ = "tax_profiles"
    
    subsidiary_id: uuid.UUID = Field(foreign_key="subsidiaries.id")
    tax_authority: str
    tax_registration_number: str
    default_tax_rate: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )

class SharingRule(BESBase, table=True):
    __tablename__ = "sharing_rules"
    
    entity_type: str = Field(index=True)  # CUSTOMER, VENDOR, ITEM
    is_globally_shared: bool = Field(default=True)

class IntercompanyAccount(BESBase, table=True):
    __tablename__ = "intercompany_accounts"
    
    from_subsidiary_id: uuid.UUID = Field(foreign_key="subsidiaries.id")
    to_subsidiary_id: uuid.UUID = Field(foreign_key="subsidiaries.id")
    due_to_account_id: uuid.UUID = Field(index=True)
    due_from_account_id: uuid.UUID = Field(index=True)

class UserInvitation(BESBase, table=True):
    __tablename__ = "user_invitations"
    
    email: str = Field(index=True)
    role_id: uuid.UUID = Field(foreign_key="roles.id")
    token: str = Field(index=True, unique=True)
    expires_at: datetime
    status: str = Field(default="PENDING")  # PENDING, ACCEPTED, EXPIRED

class UserSubsidiaryMapping(BESBase, table=True):
    __tablename__ = "user_subsidiary_mappings"
    
    user_id: uuid.UUID = Field(foreign_key="users.id")
    allowed_subsidiary_id: uuid.UUID = Field(foreign_key="subsidiaries.id")

