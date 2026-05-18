from fastapi import APIRouter, Depends
from core.auth import get_current_user
from core.models import User
from core.rbac import get_simplified_json

from acme_corp.bootstrap import CLIENT_CONFIG, LICENSED_MODULES

router = APIRouter()

@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "client": CLIENT_CONFIG.get("client_name"),
        "version": "0.1.0",
        "modules_loaded": len(LICENSED_MODULES),
    }

@router.get("/api/v1/bootstrap")
async def bootstrap(user: User = Depends(get_current_user)):
    """
    Returns the client configuration and the authenticated user's permissions,
    filtered to only the licensed modules for this client instance.
    """
    user_perms = get_simplified_json(user, licensed_modules=LICENSED_MODULES)

    return {
        "status": "success",
        "data": {
            "client_name": CLIENT_CONFIG.get("client_name"),
            "active_modules": LICENSED_MODULES,
            "user_id": str(user.id),
            "username": user.username,
            "permissions": user_perms["permissions"],
        }
    }
