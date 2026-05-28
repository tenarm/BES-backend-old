import uuid
from datetime import datetime
from typing import Optional, Any
from sqlmodel import Field
from sqlalchemy import Column, JSON

from .base import BESBase


# --- Core Domain Models ---

class Role(BESBase, table=True):
    """
    Role-based access control: each role defines a permission set
    stored as a nested JSON structure matching admin_permissions.json format.
    """
    __tablename__ = "roles"
    name: str = Field(index=True, unique=True)  # e.g., 'admin', 'manager', 'staff'
    description: Optional[str] = None
    permissions: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)


class User(BESBase, table=True):
    __tablename__ = "users"
    username: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    full_name: Optional[str] = None
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    role_id: Optional[uuid.UUID] = Field(default=None, foreign_key="roles.id")
    custom_permissions: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)


class RefreshToken(BESBase, table=True):
    """
    Stores issued refresh tokens for revocation support.
    Each row represents one active refresh token.
    """
    __tablename__ = "refresh_tokens"
    token: str = Field(index=True, unique=True)
    user_id: uuid.UUID = Field(foreign_key="users.id")
    expires_at: datetime
    is_revoked: bool = Field(default=False)
