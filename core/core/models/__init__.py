"""core.models — re-exports all model classes for backward compatibility."""

from .base import BESBase, utc_now
from .auth import User, Role, RefreshToken
from .master_data import Customer, Vendor, Product, UOM

# --- Register Notification Models ---
from ..notifications import NotificationRule, Notification

__all__ = [
    "BESBase",
    "utc_now",
    "User",
    "Role",
    "RefreshToken",
    "Customer",
    "Vendor",
    "Product",
    "UOM",
    "NotificationRule",
    "Notification",
]
