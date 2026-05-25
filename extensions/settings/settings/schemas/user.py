import uuid
from typing import Optional, Any
from datetime import datetime
from sqlmodel import SQLModel

class UserCreate(SQLModel):
    username: str
    email: str
    full_name: Optional[str] = None
    password: str
    role_id: Optional[uuid.UUID] = None
    primary_subsidiary_id: Optional[str] = None
    allowed_subsidiary_ids: Optional[list[uuid.UUID]] = None

class UserRead(SQLModel):
    id: uuid.UUID
    username: str
    email: str
    full_name: Optional[str] = None
    is_active: bool
    is_superuser: bool
    role_id: Optional[uuid.UUID] = None
    primary_subsidiary_id: Optional[str] = None
    allowed_subsidiary_ids: list[uuid.UUID]
    version_id: int

class UserUpdate(SQLModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role_id: Optional[uuid.UUID] = None
    primary_subsidiary_id: Optional[str] = None
    allowed_subsidiary_ids: Optional[list[uuid.UUID]] = None

class UserStatusUpdate(SQLModel):
    is_active: bool

class UserPasswordReset(SQLModel):
    new_password: str

class RoleCreate(SQLModel):
    name: str
    description: Optional[str] = None
    permissions: dict[str, Any] = {}

class RoleRead(SQLModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    permissions: dict[str, Any]
    version_id: int

class RoleUpdate(SQLModel):
    description: Optional[str] = None
    permissions: Optional[dict[str, Any]] = None

class SSOConfigCreate(SQLModel):
    idp_type: str
    entry_point: Optional[str] = None
    issuer: Optional[str] = None
    certificate: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    discovery_url: Optional[str] = None
    is_active: bool = True

class SSOConfigRead(SQLModel):
    id: uuid.UUID
    idp_type: str
    entry_point: Optional[str] = None
    issuer: Optional[str] = None
    certificate: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    discovery_url: Optional[str] = None
    is_active: bool
    version_id: int

class APIKeyCreate(SQLModel):
    name: str
    expires_at: Optional[datetime] = None

class APIKeyRead(SQLModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    user_id: uuid.UUID
    expires_at: Optional[datetime] = None
    is_active: bool
    version_id: int

class APIKeyCreatedResponse(SQLModel):
    id: uuid.UUID
    key_prefix: str
    plaintext_key: str
