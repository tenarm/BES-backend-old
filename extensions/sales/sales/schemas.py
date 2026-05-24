import uuid
from datetime import datetime
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator

class SalesEntityCreate(BaseModel):
    name: str
    description: str = ""

class SalesEntityRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str

# Customer Schemas
class CustomerCreate(BaseModel):
    name: str = Field(..., max_length=255)
    tax_id: Optional[str] = Field(default=None, max_length=100)
    primary_email: Optional[str] = Field(default=None, max_length=255)
    parent_customer_id: Optional[uuid.UUID] = None

    @field_validator("tax_id")
    @classmethod
    def validate_tax_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            # Simple sanitization/validation: must contain only alphanumeric characters and hyphens
            sanitized = v.strip()
            if not sanitized:
                return None
            # Validate format (optional, e.g. length minimum 4)
            if len(sanitized) < 4:
                raise ValueError("Tax ID must be at least 4 characters long")
            return sanitized
        return v

class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    tax_id: Optional[str] = Field(default=None, max_length=100)
    primary_email: Optional[str] = Field(default=None, max_length=255)
    parent_customer_id: Optional[uuid.UUID] = None
    status: Optional[str] = Field(default=None) # ACTIVE, INACTIVE
    version_id: int

class CustomerRead(BaseModel):
    id: uuid.UUID
    name: str
    tax_id: Optional[str] = None
    primary_email: Optional[str] = None
    parent_customer_id: Optional[uuid.UUID] = None
    status: str
    version_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Customer Address Schemas
class CustomerAddressCreate(BaseModel):
    address_type: str = Field(..., pattern="^(BILLING|SHIPPING)$")
    street_address: str = Field(..., max_length=512)
    city: str = Field(..., max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=20)
    country_code: str = Field(..., min_length=2, max_length=2)
    is_default: bool = False

class CustomerAddressUpdate(BaseModel):
    address_type: Optional[str] = Field(default=None, pattern="^(BILLING|SHIPPING)$")
    street_address: Optional[str] = Field(default=None, max_length=512)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=20)
    country_code: Optional[str] = Field(default=None, min_length=2, max_length=2)
    is_default: Optional[bool] = None
    version_id: int

class CustomerAddressRead(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    address_type: str
    street_address: str
    city: str
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country_code: str
    is_default: bool
    version_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Customer Contact Schemas
class CustomerContactCreate(BaseModel):
    first_name: str = Field(..., max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    department: Optional[str] = Field(default=None, max_length=100)

class CustomerContactUpdate(BaseModel):
    first_name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    department: Optional[str] = Field(default=None, max_length=100)
    version_id: int

class CustomerContactRead(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    first_name: str
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    version_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Customer Credit Schemas
class CustomerCreditUpdate(BaseModel):
    credit_limit: Decimal = Field(..., ge=0)
    payment_terms_code: Optional[str] = Field(default=None, max_length=50)
    version_id: int

class CustomerCreditRead(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    credit_limit: Decimal
    outstanding_balance: Decimal
    payment_terms_code: Optional[str] = None
    status: str
    version_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
