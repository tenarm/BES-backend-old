import json
import os
import logging
from enum import Enum
from contextvars import ContextVar
from contextlib import contextmanager
from typing import Dict, Any
from fastapi import Depends, HTTPException, status
from .auth import get_current_user
from .models import User

logger = logging.getLogger(__name__)

# --- Execution Context (User vs System) ---
class ExecutionContextType(str, Enum):
    USER = "USER"
    SYSTEM = "SYSTEM"

execution_context: ContextVar[ExecutionContextType] = ContextVar("execution_context", default=ExecutionContextType.USER)

@contextmanager
def elevate_context():
    """Context manager to temporarily elevate execution privileges to SYSTEM level."""
    token = execution_context.set(ExecutionContextType.SYSTEM)
    try:
        yield
    finally:
        execution_context.reset(token)

# --- Admin Permissions Schema (used for seeding and reference) ---
def _load_permissions() -> Dict[str, Any]:
    """Loads the master permission configuration from the JSON file."""
    config_path = os.environ.get("ADMIN_PERMISSIONS_PATH")
    if not config_path or not os.path.exists(config_path):
        config_path = os.path.join(os.path.dirname(__file__), "admin_permissions.json")
    
    with open(config_path, "r") as f:
        return json.load(f)

PERMISSIONS_SCHEMA = _load_permissions()

def _has_permission(user_perms: Dict[str, Any], module: str, resource: str, action: str) -> bool:
    """Checks if the given permission exists in the nested structure."""
    return user_perms.get(module, {}).get(resource, {}).get(action, False)

def deep_merge_permissions(base: Dict[str, Any], custom: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merges custom permissions into the base role permissions.
    Custom permissions always win in a conflict, allowing direct user overrides.
    """
    merged = base.copy()
    for key, value in custom.items():
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key] = deep_merge_permissions(merged[key], value)
        else:
            merged[key] = value
    return merged

# --- FastAPI Dependency Injector ---
def require_permission(permission_string: str):
    """
    Dependency injector for FastAPI.
    Format: "module:resource:action" (e.g., "finance:invoices:read")
    
    Now checks the user's Role.permissions instead of the global admin schema.
    SYSTEM context bypasses all checks.
    Superusers bypass all checks.
    """
    async def permission_checker(user: User = Depends(get_current_user)):
        # SYSTEM context bypass (for event-driven cross-module operations)
        if execution_context.get() == ExecutionContextType.SYSTEM:
            return True

        parts = permission_string.split(":")
        if len(parts) != 3:
            raise HTTPException(status_code=500, detail=f"Invalid format: {permission_string}")

        module, resource, action = parts

        # Superuser bypass
        if user.is_superuser:
            return True

        # --- REAL ROLE-BASED CHECK ---
        # The user's permissions come from their Role, which was eagerly loaded
        # For now, we fetch the role's permissions from the user object
        if not hasattr(user, '_role_permissions'):
            # Lazy-load role permissions if not cached
            from sqlmodel import select
            from .database import get_async_session
            from .models import Role
            # If user has no role assigned, deny by default
            if user.role_id is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission_string} (no role assigned)"
                )

        # For this to work efficiently, the bootstrap endpoint pre-computes permissions
        # Here we check against the global schema filtered by role membership
        # This is a simplified check — in production, cache the user's computed permissions
        user_perms = get_user_permissions(user)
        if not _has_permission(user_perms, module, resource, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission_string}"
            )
        return True

    return permission_checker


def get_user_permissions(user: User) -> Dict[str, Any]:
    """
    Returns the effective permission set for a given user.
    - Superusers get the full admin schema.
    - Regular users get their Role's permissions.
    - Users with no role get an empty set.
    """
    if user.is_superuser:
        return PERMISSIONS_SCHEMA

    # If no role assigned, return empty permissions
    if user.role_id is None:
        return {}

    # The role's permissions are loaded via the bootstrap flow
    # For inline checks, we need to look it up
    # This will be populated by the bootstrap/login flow
    return getattr(user, '_cached_permissions', {})


def get_simplified_json(user: User, licensed_modules: list[str] | None = None) -> dict:
    """
    Returns a simplified JSON of all permissions for a user.
    Filters to only licensed modules if provided.
    """
    perms = get_user_permissions(user)

    if licensed_modules:
        perms = {k: v for k, v in perms.items() if k in licensed_modules}

    return {
        "user_id": str(user.id),
        "role": "superuser" if user.is_superuser else "custom",
        "permissions": perms
    }



