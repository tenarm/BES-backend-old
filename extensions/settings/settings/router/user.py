import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from core.database import get_async_session
from core.responses import success_response, paginated_response
from core.pagination import PaginationParams
from core.licensing import require_licensed_feature
from core.rbac import require_permission
from core.exceptions import ConcurrencyError
from core.auth import get_current_user
from core.models import User, RefreshToken

from ..schemas import (
    UserCreate, UserUpdate, UserStatusUpdate, UserPasswordReset,
    RoleCreate, RoleUpdate, SSOConfigCreate, APIKeyCreate
)
from ..services import (
    UserService, RoleService, APIKeyService, SSOConfigurationService,
    LastAdminDeactivationError, SelfDeactivationError, WeakPasswordError,
    DuplicateRoleNameError, RoleAssignedToUsersError
)

router = APIRouter()

# --- User Management Endpoints ---

@router.get("/users", dependencies=[Depends(require_permission("settings:user_management:read"))])
async def list_users(
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("settings", "user_management")
    users, total = await UserService.list_users(session, search, is_active, pagination.page, pagination.page_size)
    return paginated_response(data=users, total=total, page=pagination.page, page_size=pagination.page_size)

@router.get("/users/{id}", dependencies=[Depends(require_permission("settings:user_management:read"))])
async def get_user(id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("settings", "user_management")
    user = await UserService.get_user(session, id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return success_response(data=user)

@router.post("/users", dependencies=[Depends(require_permission("settings:user_management:write"))])
async def create_user(data: UserCreate, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("settings", "user_management")
    try:
        user = await UserService.create_user(session, data)
        return success_response(data=user)
    except (ValueError, WeakPasswordError) as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/users/{id}", dependencies=[Depends(require_permission("settings:user_management:write"))])
async def update_user(
    id: uuid.UUID,
    data: UserUpdate,
    version_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("settings", "user_management")
    try:
        user = await UserService.update_user(session, id, data, version_id)
        return success_response(data=user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConcurrencyError as e:
        raise HTTPException(status_code=409, detail=str(e))

@router.patch("/users/{id}/status", dependencies=[Depends(require_permission("settings:user_management:write"))])
async def update_user_status(
    id: uuid.UUID,
    data: UserStatusUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    require_licensed_feature("settings", "user_management")
    try:
        user = await UserService.update_user_status(session, id, data.is_active, current_user.id)
        return success_response(data=user)
    except (SelfDeactivationError, LastAdminDeactivationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.patch("/users/{id}/password", dependencies=[Depends(require_permission("settings:user_management:write"))])
async def reset_user_password(
    id: uuid.UUID,
    data: UserPasswordReset,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("settings", "user_management")
    try:
        await UserService.reset_password(session, id, data.new_password)
        return success_response(data={"detail": "Password reset successfully."})
    except WeakPasswordError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/users/{id}/sessions", dependencies=[Depends(require_permission("settings:user_management:read"))])
async def list_user_sessions(id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("settings", "user_management")
    stmt = select(RefreshToken).where(
        RefreshToken.user_id == id,
        RefreshToken.is_revoked == False
    )
    res = await session.execute(stmt)
    tokens = res.scalars().all()
    sessions = [
        {
            "id": str(t.id),
            "token_prefix": t.token[:12] + "...",
            "expires_at": t.expires_at.isoformat()
        }
        for t in tokens
    ]
    return success_response(data=sessions)

@router.delete("/users/{id}/sessions/{session_id}", dependencies=[Depends(require_permission("settings:user_management:write"))])
async def revoke_user_session(id: uuid.UUID, session_id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("settings", "user_management")
    stmt = select(RefreshToken).where(
        RefreshToken.id == session_id,
        RefreshToken.user_id == id
    )
    res = await session.execute(stmt)
    token = res.scalars().first()
    if not token:
        raise HTTPException(status_code=404, detail="Active session token not found.")
    token.is_revoked = True
    session.add(token)
    await session.commit()
    return success_response(data={"detail": "Session successfully revoked."})

@router.delete("/users/{id}/sessions", dependencies=[Depends(require_permission("settings:user_management:write"))])
async def revoke_all_user_sessions(id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("settings", "user_management")
    stmt = select(RefreshToken).where(
        RefreshToken.user_id == id,
        RefreshToken.is_revoked == False
    )
    res = await session.execute(stmt)
    tokens = res.scalars().all()
    for t in tokens:
        t.is_revoked = True
        session.add(t)
    await session.commit()
    return success_response(data={"detail": f"Successfully revoked {len(tokens)} sessions."})

# --- Role Management Endpoints ---

@router.get("/roles", dependencies=[Depends(require_permission("settings:user_management:read"))])
async def list_roles(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("settings", "user_management")
    roles, total = await RoleService.list_roles(session, pagination.page, pagination.page_size)
    return paginated_response(data=roles, total=total, page=pagination.page, page_size=pagination.page_size)

@router.get("/roles/{id}", dependencies=[Depends(require_permission("settings:user_management:read"))])
async def get_role(id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("settings", "user_management")
    role = await RoleService.get_role(session, id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found.")
    return success_response(data=role)

@router.post("/roles", dependencies=[Depends(require_permission("settings:user_management:write"))])
async def create_role(data: RoleCreate, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("settings", "user_management")
    try:
        role = await RoleService.create_role(session, data)
        return success_response(data=role)
    except DuplicateRoleNameError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/roles/{id}", dependencies=[Depends(require_permission("settings:user_management:write"))])
async def update_role(
    id: uuid.UUID,
    data: RoleUpdate,
    version_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("settings", "user_management")
    try:
        role = await RoleService.update_role(session, id, data, version_id)
        return success_response(data=role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConcurrencyError as e:
        raise HTTPException(status_code=409, detail=str(e))

@router.delete("/roles/{id}", dependencies=[Depends(require_permission("settings:user_management:delete"))])
async def delete_role(id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("settings", "user_management")
    try:
        await RoleService.delete_role(session, id)
        return success_response(data={"detail": "Role deleted successfully."})
    except RoleAssignedToUsersError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# --- SSO Configuration Endpoints ---

@router.get("/sso", dependencies=[Depends(require_permission("settings:user_management:read"))])
async def get_sso_config(session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("settings", "user_management")
    config = await SSOConfigurationService.get_config(session)
    if not config:
        raise HTTPException(status_code=404, detail="SSO configuration not found.")
    return success_response(data=config)

@router.post("/sso", dependencies=[Depends(require_permission("settings:sso:write"))])
async def save_sso_config(data: SSOConfigCreate, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("settings", "user_management")
    config = await SSOConfigurationService.save_config(session, data)
    return success_response(data=config)

# --- API Keys Configuration Endpoints ---

@router.post("/api-keys", dependencies=[Depends(require_permission("settings:api_keys:write"))])
async def generate_api_key(data: APIKeyCreate, session: AsyncSession = Depends(get_async_session), current_user: User = Depends(get_current_user)):
    require_licensed_feature("settings", "user_management")
    try:
        key_obj, plaintext = await APIKeyService.generate_key(session, data.name, current_user.id, data.expires_at)
        return success_response(data={
            "id": str(key_obj.id),
            "key_prefix": key_obj.key_prefix,
            "plaintext_key": plaintext
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/api-keys/{id}", dependencies=[Depends(require_permission("settings:api_keys:write"))])
async def revoke_api_key(id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("settings", "user_management")
    try:
        await APIKeyService.revoke_key(session, id)
        return success_response(data={"detail": "API Key revoked successfully."})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
