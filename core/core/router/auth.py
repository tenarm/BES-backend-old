import os
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from ..database import get_async_session
from ..models import User, Role, RefreshToken
from ..auth import (
    create_access_token, create_refresh_token, decode_token,
    verify_password, get_current_user, get_password_hash
)
from ..rbac import get_user_permissions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# --- Schemas ---
class RefreshRequest(BaseModel):
    refresh_token: str

class RevokeRequest(BaseModel):
    refresh_token: str


# --- Login ---
@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    stmt = select(User).where(User.username == form_data.username)
    result = await session.execute(stmt)
    user = result.scalars().first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )

    access_token = create_access_token(data={"sub": user.username})
    refresh_token, refresh_expires = create_refresh_token(data={"sub": user.username})

    # Store refresh token in DB for revocation support
    db_refresh = RefreshToken(
        token=refresh_token,
        user_id=user.id,
        expires_at=refresh_expires
    )
    session.add(db_refresh)
    await session.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


# --- Refresh Token ---
@router.post("/refresh")
async def refresh(
    body: RefreshRequest,
    session: AsyncSession = Depends(get_async_session)
):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Check if token is revoked
    stmt = select(RefreshToken).where(
        RefreshToken.token == body.refresh_token,
        RefreshToken.is_revoked == False
    )
    result = await session.execute(stmt)
    db_token = result.scalars().first()
    if not db_token:
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")

    username = payload.get("sub")
    new_access_token = create_access_token(data={"sub": username})
    return {"access_token": new_access_token, "token_type": "bearer"}


# --- Revoke Token ---
@router.post("/revoke")
async def revoke(
    body: RevokeRequest,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(get_current_user)
):
    stmt = select(RefreshToken).where(
        RefreshToken.token == body.refresh_token,
        RefreshToken.user_id == user.id
    )
    result = await session.execute(stmt)
    db_token = result.scalars().first()
    if db_token:
        db_token.is_revoked = True
        session.add(db_token)
        await session.commit()
    return {"status": "success", "detail": "Token revoked"}


# --- Current User Profile ---
@router.get("/me")
async def get_me(
    user: User = Depends(get_current_user),
):
    """
    Returns the authenticated user's profile and their full role permission set.

    Contract:
    - Returns complete permissions for the user's assigned role.
    - Does NOT filter to licensed modules — that is the responsibility of
      /bootstrap (instance-level), which knows the client's LICENSED_MODULES.
    - No second DB query: get_current_user() already loaded
      user._cached_permissions eagerly.
    """
    permissions = get_user_permissions(user)

    return {
        "id": str(user.id),
        "username": user.username,
        "full_name": user.full_name,
        "is_superuser": user.is_superuser,
        "role_id": str(user.role_id) if user.role_id else None,
        "permissions": permissions
    }
