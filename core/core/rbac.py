import re
from enum import Enum
from contextvars import ContextVar
from contextlib import contextmanager
from typing import Dict, Any, List, Optional
from fastapi import Request, HTTPException, Depends, status
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from .database import subsidiary_id_context
import json
import os
from .auth import get_current_user
from .models import User

# --- Execution Context (User vs System) ---
class ExecutionContextType(str, Enum):
    USER = "USER"
    SYSTEM = "SYSTEM"

execution_context: ContextVar[ExecutionContextType] = ContextVar("execution_context", default=ExecutionContextType.USER)

@contextmanager
def elevate_context():
    """
    Context manager to temporarily elevate execution privileges to SYSTEM level.
    Useful for internal event handlers or background jobs that need to bypass user-level RBAC.
    """
    token = execution_context.set(ExecutionContextType.SYSTEM)
    try:
        yield
    finally:
        execution_context.reset(token)

# --- Advanced RBAC Schema ---
class ActionPermissions(BaseModel):
    read: bool = False
    write: bool = False
    delete: bool = False

class ResourcePermissions(BaseModel):
    actions: ActionPermissions

class ModulePermissions(BaseModel):
    resources: Dict[str, ResourcePermissions]

class MasterJSON(BaseModel):
    modules: Dict[str, ModulePermissions]

def _load_admin_permissions() -> MasterJSON:
    """
    Loads the admin permission configuration from the mock JSON file.
    """
    config_path = os.path.join(os.path.dirname(__file__), "admin_permissions.json")
    with open(config_path, "r") as f:
        data = json.load(f)
    return MasterJSON(**data)

MOCK_MASTER_JSON = _load_admin_permissions()

def _has_permission(master_json: MasterJSON, module: str, resource: str, action: str) -> bool:
    module_perms = master_json.modules.get(module)
    if not module_perms:
        return False
    resource_perms = module_perms.resources.get(resource)
    if not resource_perms:
        return False
    
    # action should be read, write, delete
    return getattr(resource_perms.actions, action, False)

# --- FastAPI Dependency Injector ---
def require_permission(permission_string: str):
    """
    Dependency injector for FastAPI. 
    Format: "module:resource:action" (e.g., "finance:invoices:write")
    """
    def permission_checker(user: User = Depends(get_current_user)):
        # If running in system context, bypass
        if execution_context.get() == ExecutionContextType.SYSTEM:
            return True
            
        parts = permission_string.split(":")
        if len(parts) != 3:
            raise HTTPException(status_code=500, detail=f"Invalid permission string format: {permission_string}")
        
        module, resource, action = parts
        
        # Admin bypass for this exercise
        if user.is_superuser:
            user_permissions = MOCK_MASTER_JSON # Load the full admin JSON
        else:
            # In a real app, you would fetch the user's specific MasterJSON from their role/database
            user_permissions = MOCK_MASTER_JSON
        
        if not _has_permission(user_permissions, module, resource, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail=f"Permission denied. Required: {permission_string}"
            )
        return True

    return permission_checker

# --- Middleware ---
class ContextAwareSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extract subsidiary_id from headers for multi-tenancy context
        subs_id = request.headers.get("X-Subsidiary-Id")
        if subs_id:
            token = subsidiary_id_context.set(subs_id)
        else:
            token = subsidiary_id_context.set(None)
            
        try:
            response = await call_next(request)
            return response
        finally:
            subsidiary_id_context.reset(token)

# --- Simplified JSON for UI ---
def get_simplified_json(user_id: str) -> Dict[str, Any]:
    """
    Transforms the complex Master JSON into a flat, boolean map for ultra-fast React UI rendering.
    e.g. {"finance_invoices_read": true, "finance_invoices_write": false}
    """
    user_permissions = MOCK_MASTER_JSON
    simplified = {}
    active_modules = list(user_permissions.modules.keys())
    
    for mod_name, mod_data in user_permissions.modules.items():
        for res_name, res_data in mod_data.resources.items():
            simplified[f"{mod_name}_{res_name}_read"] = res_data.actions.read
            simplified[f"{mod_name}_{res_name}_write"] = res_data.actions.write
            simplified[f"{mod_name}_{res_name}_delete"] = res_data.actions.delete
            
    return {
        "modules": active_modules,
        "permissions": simplified
    }
