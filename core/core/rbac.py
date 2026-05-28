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


# ---------------------------------------------------------------------------
# Execution context — USER vs SYSTEM
# ---------------------------------------------------------------------------

class ExecutionContextType(str, Enum):
    """Indicates whether the current call originates from a user request or an internal system action."""
    USER = "USER"
    SYSTEM = "SYSTEM"


execution_context: ContextVar[ExecutionContextType] = ContextVar(
    "execution_context", default=ExecutionContextType.USER
)


@contextmanager
def elevate_context():
    """
    Context manager that temporarily promotes execution privileges to SYSTEM level.

    Use this in event-driven handlers and background workers to bypass RBAC and
    licensing guards that are only meaningful for user-initiated requests.

    Example::

        with elevate_context():
            await order_service.auto_post_journal(session, order_id)
    """
    token = execution_context.set(ExecutionContextType.SYSTEM)
    try:
        yield
    finally:
        execution_context.reset(token)


# ---------------------------------------------------------------------------
# Permission schema (master reference for seeding and superuser resolution)
# ---------------------------------------------------------------------------

def _load_permissions() -> Dict[str, Any]:
    """Loads the master permission configuration from admin_permissions.json."""
    config_path = os.environ.get("ADMIN_PERMISSIONS_PATH")
    if not config_path or not os.path.exists(config_path):
        config_path = os.path.join(os.path.dirname(__file__), "admin_permissions.json")

    with open(config_path, "r") as f:
        return json.load(f)


PERMISSIONS_SCHEMA: Dict[str, Any] = _load_permissions()


def _has_permission(user_perms: Dict[str, Any], module: str, resource: str, action: str) -> bool:
    """Returns True if the nested permission map grants the given module/resource/action triple."""
    return user_perms.get(module, {}).get(resource, {}).get(action, False)


def deep_merge_permissions(base: Dict[str, Any], custom: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merges ``custom`` permissions into ``base``, with custom values winning on conflict.

    This allows per-user permission overrides to extend or narrow the role's default grants
    without a full replacement.

    Args:
        base:   The role-level permission dictionary.
        custom: The user-level override dictionary.

    Returns:
        A new merged dictionary; the originals are not mutated.
    """
    merged = base.copy()
    for key, value in custom.items():
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key] = deep_merge_permissions(merged[key], value)
        else:
            merged[key] = value
    return merged


# ---------------------------------------------------------------------------
# FastAPI dependency: permission gate
# ---------------------------------------------------------------------------

def require_permission(permission_string: str):
    """
    Returns a FastAPI dependency that asserts the authenticated user holds the named permission.

    Permission format: ``"module:resource:action"``  (e.g. ``"finance:invoices:read"``).

    Bypass conditions (no check performed):
    - SYSTEM execution context (event-driven cross-module operations via ``elevate_context``).
    - The user is a superuser.
    """
    async def permission_checker(user: User = Depends(get_current_user)):
        # SYSTEM context: internal automation bypasses all RBAC guards.
        if execution_context.get() == ExecutionContextType.SYSTEM:
            return True

        parts = permission_string.split(":")
        if len(parts) != 3:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Malformed permission string: '{permission_string}'. Expected 'module:resource:action'.",
            )

        module, resource, action = parts

        # Superusers are granted every permission unconditionally.
        if user.is_superuser:
            return True

        # Users with no role cannot hold any permissions.
        if user.role_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: '{permission_string}' (user has no role assigned).",
            )

        # Permissions were eagerly resolved and cached in get_current_user.
        user_perms = get_user_permissions(user)
        if not _has_permission(user_perms, module, resource, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: '{permission_string}'.",
            )
        return True

    return permission_checker


# ---------------------------------------------------------------------------
# Permission resolution helpers
# ---------------------------------------------------------------------------

def get_user_permissions(user: User) -> Dict[str, Any]:
    """
    Returns the effective permission map for a given user.

    - Superusers receive the full admin schema (all permissions granted).
    - Role-based users receive their pre-resolved ``_cached_permissions`` (set by
      ``get_current_user`` at authentication time).
    - Users with no role receive an empty map (no permissions).

    Args:
        user: The authenticated User ORM instance.

    Returns:
        A nested dictionary of the form ``{module: {resource: {action: bool}}}``.
    """
    if user.is_superuser:
        return PERMISSIONS_SCHEMA

    if user.role_id is None:
        return {}

    return getattr(user, "_cached_permissions", {})


def get_simplified_json(user: User, licensed_modules: list[str] | None = None) -> dict:
    """
    Serialises the user's effective permissions to a JSON-friendly dictionary.

    Args:
        user:              The authenticated User ORM instance.
        licensed_modules:  If provided, filters the output to only include these module keys.

    Returns:
        ``{"user_id": str, "role": str, "permissions": dict}``
    """
    perms = get_user_permissions(user)

    if licensed_modules:
        perms = {k: v for k, v in perms.items() if k in licensed_modules}

    return {
        "user_id": str(user.id),
        "role": "superuser" if user.is_superuser else "custom",
        "permissions": perms,
    }
