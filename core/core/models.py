import uuid
from datetime import datetime, timezone
from typing import Optional, Any
from decimal import Decimal
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON, Numeric, event
from sqlalchemy.orm import declared_attr


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class BESBase(SQLModel):
    """
    Unified base model for all BES tables.
    Provides UUID primary keys, audit trail, multi-org scoping,
    soft-deletion, and a JSONB expansion joint.
    """
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    created_by: Optional[str] = Field(default=None)
    subsidiary_id: Optional[str] = Field(default=None, index=True)
    is_deleted: bool = Field(default=False)
    # Using JSON for sqlite compatibility
    metadata_: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)

    # Concurrency control: Optimistic locking version field
    version_id: int = Field(
        default=1,
        sa_column_kwargs={"server_default": "1"}
    )

    @declared_attr
    def __mapper_args__(cls):
        return {
            "version_id_col": cls.version_id
        }



# --- SQLAlchemy event to auto-update `updated_at` on modification ---
@event.listens_for(BESBase, "before_update", propagate=True)
def receive_before_update(mapper, connection, target):
    """Automatically set updated_at to current UTC time before any update."""
    target.updated_at = utc_now()


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


class Customer(BESBase, table=True):
    __tablename__ = "customers"
    name: str
    tax_id: Optional[str] = None
    primary_email: Optional[str] = None


class Vendor(BESBase, table=True):
    __tablename__ = "vendors"
    name: str
    tax_id: Optional[str] = None
    primary_email: Optional[str] = None
    payment_terms: Optional[str] = None  # e.g., "Net 30"


class Product(BESBase, table=True):
    __tablename__ = "products"
    name: str
    sku: str = Field(index=True, unique=True)
    # Enforced Decimal(20,4) per ARCHITECTURE.md §7.A "Money Rule"
    base_price: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    uom_id: Optional[uuid.UUID] = Field(default=None, foreign_key="uoms.id")


class UOM(BESBase, table=True):
    __tablename__ = "uoms"
    code: str = Field(index=True, unique=True)  # e.g., 'KG', 'EA'
    name: str  # e.g., 'Kilograms', 'Each'
    description: Optional[str] = None


# --- Register Notification Models ---
from .notifications import NotificationRule, Notification


