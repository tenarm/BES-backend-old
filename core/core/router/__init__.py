"""core.router — re-exports all routers and utilities for backward compatibility."""

from .auth import router
from .audit import audit_router
from .notifications import notification_router
from .seeds import seed_roles, seed_admin_user, cleanup_expired_tokens

__all__ = [
    "router",
    "audit_router",
    "notification_router",
    "seed_roles",
    "seed_admin_user",
    "cleanup_expired_tokens",
]
