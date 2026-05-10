import re
import json
import os
from enum import Enum
from contextvars import ContextVar
from contextlib import contextmanager
from typing import Dict, Any, List, Optional
from fastapi import Request, HTTPException, Depends, status
from starlette.middleware.base import BaseHTTPMiddleware
from .database import subsidiary_id_context
from .auth import get_current_user
from .models import User

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

# --- Simplified RBAC Loader ---
def _load_permissions() -> Dict[str, Any]:
    """Loads the permission configuration from the JSON file."""
    config_path = os.path.join(os.path.dirname(__file__), "admin_permissions.json")
    with open(config_path, "r") as f:
        return json.load(f)

PERMISSIONS_SCHEMA = _load_permissions()

def _has_permission(user_perms: Dict[str, Any], module: str, resource: str, action: str) -> bool:
    """Checks if the given permission exists in the nested structure."""
    return user_perms.get(module, {}).get(resource, {}).get(action, False)

# --- FastAPI Dependency Injector ---
def require_permission(permission_string: str):
    """
    Dependency injector for FastAPI. 
    Format: "module:resource:action" (e.g., "finance:invoices:read")
    """
    def permission_checker(user: User = Depends(get_current_user)):
        if execution_context.get() == ExecutionContextType.SYSTEM:
            return True
            
        parts = permission_string.split(":")
        if len(parts) != 3:
            raise HTTPException(status_code=500, detail=f"Invalid format: {permission_string}")
        
        module, resource, action = parts
        
        # Superuser bypass
        if user.is_superuser:
            return True
        
        # In a real app, user.role would determine which subset of PERMISSIONS_SCHEMA they get
        # For this exercise, we'll assume they get the schema if they aren't restricted
        if not _has_permission(PERMISSIONS_SCHEMA, module, resource, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail=f"Permission denied: {permission_string}"
            )
        return True

    return permission_checker

# --- Simplified RBAC Loader ---
def get_simplified_json(user_id: str):
    """
    Returns a simplified JSON of all permissions for a user.
    In this prototype, we return the full schema for all users.
    """
    return {
        "user_id": user_id,
        "permissions": PERMISSIONS_SCHEMA
    }

# --- Middleware ---
class ContextAwareSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        subs_id = request.headers.get("X-Subsidiary-Id")
        token = subsidiary_id_context.set(subs_id)
        try:
            return await call_next(request)
        finally:
            subsidiary_id_context.reset(token)
