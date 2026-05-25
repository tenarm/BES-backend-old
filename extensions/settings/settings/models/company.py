import uuid
from typing import Optional
from decimal import Decimal
from sqlmodel import Field, SQLModel
from sqlalchemy import Column, Numeric
from core.models import BESBase

class CompanyProfile(BESBase, table=True):
    __tablename__ = "settings_company_profiles"
    
    legal_name: str = Field(index=True)
    dba_name: Optional[str] = Field(default=None)
    tax_identifier: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    website: Optional[str] = Field(default=None)
    default_language: str = Field(default="en")
    logo_url: Optional[str] = Field(default=None)

class Subsidiary(BESBase, table=True):
    __tablename__ = "settings_subsidiaries"
    
    name: str = Field(index=True)
    parent_id: Optional[uuid.UUID] = Field(default=None, foreign_key="settings_subsidiaries.id")
    base_currency: str = Field(default="USD")
    tax_identifier: Optional[str] = Field(default=None)
    address_billing: str = Field(default="")
    address_shipping: str = Field(default="")
    is_active: bool = Field(default=True)

class FiscalCalendar(BESBase, table=True):
    __tablename__ = "settings_fiscal_calendars"
    
    name: str = Field(index=True)
    start_date: str = Field(description="YYYY-MM-DD start boundary")
    end_date: str = Field(description="YYYY-MM-DD end boundary")
    status: str = Field(default="OPEN")  # OPEN, CLOSED

class PostingPeriod(BESBase, table=True):
    __tablename__ = "settings_posting_periods"
    
    calendar_id: uuid.UUID = Field(foreign_key="settings_fiscal_calendars.id")
    name: str = Field(index=True)
    start_date: str = Field(description="YYYY-MM-DD start boundary")
    end_date: str = Field(description="YYYY-MM-DD end boundary")
    is_locked: bool = Field(default=False)

class TaxProfile(BESBase, table=True):
    __tablename__ = "settings_tax_profiles"
    
    name: str = Field(index=True)
    jurisdiction: str = Field(index=True)
    tax_rate: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    is_active: bool = Field(default=True)
