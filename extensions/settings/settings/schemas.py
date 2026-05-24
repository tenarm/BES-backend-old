import uuid
from datetime import date, datetime
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field

# Original entity schemas (keep for compatibility)
class SettingsEntityCreate(BaseModel):
    name: str
    description: str = ""

class SettingsEntityRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str

# Company Profile Schemas
class CompanyProfileCreate(BaseModel):
    name: str
    legal_name: str
    registration_id: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    logo_light_url: Optional[str] = None
    logo_dark_url: Optional[str] = None
    primary_brand_color: Optional[str] = None
    timezone: str = "UTC"
    base_currency: str = "USD"
    date_format: str = "YYYY-MM-DD"
    number_format: str = "1,000.00"

class CompanyProfileUpdate(BaseModel):
    name: Optional[str] = None
    legal_name: Optional[str] = None
    registration_id: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    logo_light_url: Optional[str] = None
    logo_dark_url: Optional[str] = None
    primary_brand_color: Optional[str] = None
    timezone: Optional[str] = None
    base_currency: Optional[str] = None
    date_format: Optional[str] = None
    number_format: Optional[str] = None
    version_id: int

class CompanyProfileRead(BaseModel):
    id: uuid.UUID
    name: str
    legal_name: str
    registration_id: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    logo_light_url: Optional[str] = None
    logo_dark_url: Optional[str] = None
    primary_brand_color: Optional[str] = None
    timezone: str
    base_currency: str
    date_format: str
    number_format: str
    version_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Subsidiary Schemas
class SubsidiaryCreate(BaseModel):
    name: str
    legal_name: str
    tax_id: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None
    country_code: str = Field(..., min_length=2, max_length=2)
    currency_code: str = Field(..., min_length=3, max_length=3)
    status: str = "ACTIVE"

class SubsidiaryUpdate(BaseModel):
    name: Optional[str] = None
    legal_name: Optional[str] = None
    tax_id: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None
    country_code: Optional[str] = None
    currency_code: Optional[str] = None
    status: Optional[str] = None
    version_id: int

class SubsidiaryRead(BaseModel):
    id: uuid.UUID
    name: str
    legal_name: str
    tax_id: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None
    country_code: str
    currency_code: str
    status: str
    version_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Fiscal Year & Posting Period Schemas
class FiscalYearCreate(BaseModel):
    name: str
    start_date: date
    end_date: date

class FiscalYearUpdate(BaseModel):
    name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = None
    version_id: int

class FiscalYearRead(BaseModel):
    id: uuid.UUID
    name: str
    start_date: date
    end_date: date
    status: str
    version_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PostingPeriodRead(BaseModel):
    id: uuid.UUID
    fiscal_year_id: uuid.UUID
    name: str
    start_date: date
    end_date: date
    status: str
    locked_at: Optional[datetime] = None
    locked_by: Optional[uuid.UUID] = None
    version_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Tax Profile Schemas
class TaxProfileCreate(BaseModel):
    subsidiary_id: uuid.UUID
    tax_authority: str
    tax_registration_number: str
    default_tax_rate: Decimal = Field(default=Decimal("0.0"), decimal_places=4)

class TaxProfileUpdate(BaseModel):
    tax_authority: Optional[str] = None
    tax_registration_number: Optional[str] = None
    default_tax_rate: Optional[Decimal] = None
    version_id: int

class TaxProfileRead(BaseModel):
    id: uuid.UUID
    subsidiary_id: uuid.UUID
    tax_authority: str
    tax_registration_number: str
    default_tax_rate: Decimal
    version_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Sharing Rule Schemas
class SharingRuleUpdate(BaseModel):
    entity_type: str
    is_globally_shared: bool
    version_id: int

class SharingRuleRead(BaseModel):
    id: uuid.UUID
    entity_type: str
    is_globally_shared: bool
    version_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Intercompany Account Schemas
class IntercompanyAccountCreate(BaseModel):
    from_subsidiary_id: uuid.UUID
    to_subsidiary_id: uuid.UUID
    due_to_account_id: uuid.UUID
    due_from_account_id: uuid.UUID

class IntercompanyAccountRead(BaseModel):
    id: uuid.UUID
    from_subsidiary_id: uuid.UUID
    to_subsidiary_id: uuid.UUID
    due_to_account_id: uuid.UUID
    due_from_account_id: uuid.UUID
    version_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- User Management Schemas ---

class UserInviteRequest(BaseModel):
    email: str
    role_id: uuid.UUID

class UserInvitationRead(BaseModel):
    id: uuid.UUID
    email: str
    role_id: uuid.UUID
    token: str
    expires_at: datetime
    status: str
    version_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class UserUpdatePayload(BaseModel):
    full_name: Optional[str] = None
    role_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None
    allowed_subsidiary_ids: Optional[list[uuid.UUID]] = None
    version_id: int

class UserReadPayload(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    full_name: Optional[str] = None
    is_active: bool
    role_id: Optional[uuid.UUID] = None
    allowed_subsidiary_ids: list[uuid.UUID] = []
    version_id: int

    class Config:
        from_attributes = True

class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    permissions: dict = {}

class RoleUpdate(BaseModel):
    description: Optional[str] = None
    permissions: Optional[dict] = None
    version_id: int

class RoleRead(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    permissions: dict
    version_id: int

    class Config:
        from_attributes = True

class SessionRead(BaseModel):
    id: uuid.UUID
    token: str
    expires_at: datetime
    is_revoked: bool
    version_id: int

    class Config:
        from_attributes = True

