import os
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from .database import get_async_session
from .models import User, Role, RefreshToken
from .auth import (
    create_access_token, create_refresh_token, decode_token,
    verify_password, get_current_user, get_password_hash
)
from .rbac import PERMISSIONS_SCHEMA, get_user_permissions, generate_manager_permissions, generate_staff_permissions

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
    session: AsyncSession = Depends(get_async_session)
):
    # Load the user's role permissions
    permissions = {}
    if user.is_superuser:
        permissions = PERMISSIONS_SCHEMA
    elif user.role_id:
        role_stmt = select(Role).where(Role.id == user.role_id)
        role_result = await session.execute(role_stmt)
        role = role_result.scalars().first()
        if role:
            permissions = role.permissions

    return {
        "id": str(user.id),
        "username": user.username,
        "full_name": user.full_name,
        "is_superuser": user.is_superuser,
        "role_id": str(user.role_id) if user.role_id else None,
        "permissions": permissions
    }


# --- Audit Timeline Endpoints ---
@router.get("/audit/{entity_type}/{entity_id}")
async def get_entity_audit_timeline(
    entity_type: str,
    entity_id: str,
    page: int = 1,
    page_size: int = 50,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Returns the full audit timeline for a specific entity. Feeds the frontend Timeline."""
    from .audit import AuditService
    timeline = await AuditService.get_entity_timeline(session, entity_type, entity_id, page, page_size)
    return {"status": "success", "data": timeline}


@router.get("/audit/chain/{correlation_id}")
async def get_correlation_chain(
    correlation_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Returns all audit entries linked by a correlation ID (full causal chain)."""
    from .audit import AuditService
    chain = await AuditService.get_correlation_chain(session, correlation_id)
    return {"status": "success", "data": chain}


# --- SSE: Real-Time Activity Stream ---
@router.get("/audit/stream")
async def audit_sse_stream(
    module: str | None = None,
    entity_type: str | None = None,
    user: User = Depends(get_current_user),
):
    """
    Server-Sent Events stream for real-time audit activity.
    The frontend connects once and receives live audit entries as they happen.

    Optional filters:
      ?module=finance     — only finance module events
      ?entity_type=finance.JournalEntry — only journal entry events

    Usage (frontend):
      const es = new EventSource('/api/v1/auth/audit/stream?module=finance');
      es.onmessage = (e) => { const entry = JSON.parse(e.data); ... };
    """
    import asyncio
    import json
    from starlette.responses import StreamingResponse
    from .audit import audit_broadcaster

    queue = audit_broadcaster.subscribe()

    async def event_generator():
        try:
            # Send initial keepalive
            yield f"event: connected\ndata: {json.dumps({'status': 'connected', 'user': user.username})}\n\n"

            while True:
                try:
                    entry = await asyncio.wait_for(queue.get(), timeout=30.0)
                    # Apply filters
                    if module and entry.get("module") != module:
                        continue
                    if entity_type and entry.get("entity_type") != entity_type:
                        continue
                    yield f"data: {json.dumps(entry, default=str)}\n\n"
                except asyncio.TimeoutError:
                    # Keepalive to prevent connection timeout
                    yield f": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            audit_broadcaster.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


# --- Seed Functions ---
async def seed_roles(session: AsyncSession):
    """Seeds default roles if they don't exist."""
    roles_to_seed = [
        {
            "name": "admin",
            "description": "Full administrative access to all modules and actions",
            "permissions": PERMISSIONS_SCHEMA
        },
        {
            "name": "manager",
            "description": "Read and write access to all modules, no delete privileges",
            "permissions": generate_manager_permissions()
        },
        {
            "name": "staff",
            "description": "Read-only access across all licensed modules",
            "permissions": generate_staff_permissions()
        }
    ]

    for role_data in roles_to_seed:
        stmt = select(Role).where(Role.name == role_data["name"])
        result = await session.execute(stmt)
        if not result.scalars().first():
            role = Role(**role_data)
            session.add(role)
            logger.info(f"Seeded role: {role_data['name']}")

    await session.commit()


async def seed_admin_user(session: AsyncSession):
    """
    Seeds an admin user if none exists.
    Password is sourced from INITIAL_ADMIN_PASSWORD env var.
    Falls back to 'admin123' ONLY in development (when DEBUG=true).
    """
    stmt = select(User).where(User.username == "admin")
    result = await session.execute(stmt)
    if result.scalars().first():
        return  # Admin already exists

    admin_password = os.environ.get("INITIAL_ADMIN_PASSWORD")
    is_debug = os.getenv("DEBUG", "false").lower() == "true"

    if not admin_password:
        if is_debug:
            admin_password = "admin123"
            logger.warning("DEBUG MODE: Using default admin password 'admin123'. DO NOT use in production.")
        else:
            logger.info("No INITIAL_ADMIN_PASSWORD set and DEBUG is off. Skipping admin seed.")
            return

    # Find the admin role
    role_stmt = select(Role).where(Role.name == "admin")
    role_result = await session.execute(role_stmt)
    admin_role = role_result.scalars().first()

    admin = User(
        username="admin",
        email="admin@bes.com",
        hashed_password=get_password_hash(admin_password),
        full_name="System Administrator",
        is_superuser=True,
        role_id=admin_role.id if admin_role else None
    )
    session.add(admin)
    await session.commit()
    logger.info("Seeded admin user")
