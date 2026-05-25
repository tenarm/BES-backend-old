import uuid
from typing import Optional
from datetime import datetime
from sqlmodel import Field
from sqlalchemy import UniqueConstraint
from core.models import BESBase

class UserSubsidiaryAccess(BESBase, table=True):
    __tablename__ = "settings_user_subsidiary_access"
    __table_args__ = (
        UniqueConstraint("user_id", "subsidiary_id", name="uq_user_subsidiary"),
    )
    
    user_id: uuid.UUID = Field(index=True, foreign_key="users.id")
    subsidiary_id: uuid.UUID = Field(index=True, foreign_key="settings_subsidiaries.id")

class SSOConfiguration(BESBase, table=True):
    __tablename__ = "settings_sso_configurations"
    
    idp_type: str = Field(max_length=20) # "SAML" | "OIDC"
    entry_point: Optional[str] = Field(default=None, max_length=500)
    issuer: Optional[str] = Field(default=None, max_length=255)
    certificate: Optional[str] = Field(default=None)
    client_id: Optional[str] = Field(default=None, max_length=255)
    client_secret: Optional[str] = Field(default=None, max_length=255)
    discovery_url: Optional[str] = Field(default=None, max_length=500)
    is_active: bool = Field(default=True)

class APIKey(BESBase, table=True):
    __tablename__ = "settings_api_keys"
    
    name: str = Field(max_length=100)
    key_prefix: str = Field(max_length=16) # e.g. "bes_live_"
    hashed_key: str = Field(index=True, max_length=64) # SHA-256 hash of secret
    user_id: uuid.UUID = Field(foreign_key="users.id")
    expires_at: Optional[datetime] = Field(default=None)
    is_active: bool = Field(default=True)
