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
from .rbac import PERMISSIONS_SCHEMA, get_user_permissions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

# Fix #10: Audit endpoints separated from auth endpoints.
# Auth = identity (login/refresh/revoke/me).
# Audit = observability (timelines, chains, SSE stream).
audit_router = APIRouter(prefix="/api/v1/audit", tags=["Audit & Observability"])


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


# --- Audit Timeline Endpoints (on audit_router, not auth router) ---
@audit_router.get("/{entity_type}/{entity_id}")
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


@audit_router.get("/chain/{correlation_id}")
async def get_correlation_chain(
    correlation_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Returns all audit entries linked by a correlation ID (full causal chain)."""
    from .audit import AuditService
    chain = await AuditService.get_correlation_chain(session, correlation_id)
    return {"status": "success", "data": chain}


@audit_router.get("/processes", response_model=dict)
async def get_processes(
    module: str | None = None,
    user: User = Depends(get_current_user)
):
    """
    Returns process workflow schema definitions.
    Can be optionally filtered by module (e.g., ?module=finance).
    Definitions are dynamically filtered and resolved based on client licenses.
    """
    from .processes import PROCESS_DEFINITIONS, resolve_process_for_client
    
    # Resolve definitions for the active client context
    resolved_defs = {
        pid: resolve_process_for_client(pdef)
        for pid, pdef in PROCESS_DEFINITIONS.items()
    }
    
    if module:
        module_procs = {
            pid: pdef for pid, pdef in resolved_defs.items()
            if pdef.get("module") == module
        }
        return {"status": "success", "data": module_procs}
    return {"status": "success", "data": resolved_defs}


@audit_router.get("/processes/{process_id}", response_model=dict)
async def get_process_definition(
    process_id: str,
    user: User = Depends(get_current_user)
):
    """Returns the process workflow schema definition for the given process_id."""
    from .processes import PROCESS_DEFINITIONS, resolve_process_for_client
    definition = PROCESS_DEFINITIONS.get(process_id)
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Process definition for '{process_id}' not found."
        )
    return {"status": "success", "data": resolve_process_for_client(definition)}


# --- SSE: Real-Time Activity Stream (on audit_router) ---
@audit_router.get("/stream")
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


async def cleanup_expired_tokens(session: AsyncSession) -> int:
    """
    Fix #14: Purges revoked and expired RefreshToken rows.

    RefreshToken rows accumulate indefinitely without cleanup. Call this
    from the instance lifespan (e.g., on startup or via a scheduler) to
    keep the table lean and revocation checks fast.

    Returns the number of rows deleted.
    """
    from sqlalchemy import delete as sa_delete
    from datetime import datetime, timezone

    cutoff = datetime.now(timezone.utc)
    stmt = sa_delete(RefreshToken).where(
        (RefreshToken.is_revoked == True) |  # noqa: E712
        (RefreshToken.expires_at < cutoff)
    )
    result = await session.execute(stmt)
    await session.commit()
    deleted = result.rowcount
    if deleted:
        logger.info(f"[TokenCleanup] Purged {deleted} expired/revoked refresh tokens.")
    return deleted


# ─── Notifications Router ───────────────────────────────────────────────────
import uuid
from datetime import datetime, timezone
from sqlalchemy import func
from .pagination import PaginationParams
from .responses import StandardResponse, success_response, paginated_response
from .licensing import require_licensed_feature
from .notifications import Notification, NotificationRule

notification_router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])

class NotificationRuleCreate(BaseModel):
    event_type: str
    channel: str  # "IN_APP" | "EMAIL"
    template_title: str
    template_body: str
    recipient_type: str  # "USER" | "ROLE" | "PAYLOAD_FIELD"
    recipient_target: str
    is_active: bool = True


@notification_router.get("", response_model=StandardResponse)
async def list_notifications(
    user: User = Depends(get_current_user),
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Lists paginated notifications for the currently logged in user.
    """
    stmt = select(Notification).where(
        Notification.user_id == user.id,
        Notification.is_deleted == False
    )
    
    # Get total count
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await session.execute(count_stmt)
    total = total_result.scalar() or 0

    # Get paginated data ordered by created_at desc
    query_stmt = stmt.order_by(Notification.created_at.desc()).offset(pagination.offset).limit(pagination.limit)
    result = await session.execute(query_stmt)
    notifications = result.scalars().all()

    return paginated_response(
        data=[
            {
                "id": str(n.id),
                "created_at": n.created_at.isoformat(),
                "title": n.title,
                "body": n.body,
                "channel": n.channel,
                "status": n.status,
                "read_at": n.read_at.isoformat() if n.read_at else None,
            }
            for n in notifications
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size
    )


@notification_router.post("/{id}/read", response_model=StandardResponse)
async def mark_as_read(
    id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Marks a specific notification as read.
    """
    stmt = select(Notification).where(
        Notification.id == id,
        Notification.user_id == user.id,
        Notification.is_deleted == False
    )
    result = await session.execute(stmt)
    notif = result.scalars().first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    notif.status = "READ"
    notif.read_at = datetime.now(timezone.utc)
    session.add(notif)
    await session.commit()
    return success_response({"id": str(notif.id), "status": notif.status})


@notification_router.post("/read-all", response_model=StandardResponse)
async def mark_all_as_read(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Marks all notifications for the authenticated user as read.
    """
    stmt = select(Notification).where(
        Notification.user_id == user.id,
        Notification.status != "READ",
        Notification.is_deleted == False
    )
    result = await session.execute(stmt)
    notifications = result.scalars().all()

    now = datetime.now(timezone.utc)
    for notif in notifications:
        notif.status = "READ"
        notif.read_at = now
        session.add(notif)

    await session.commit()
    return success_response({"count": len(notifications)})


@notification_router.get("/stream")
async def notifications_sse_stream(
    user: User = Depends(get_current_user),
):
    """
    Server-Sent Events endpoint to stream real-time notifications for the authenticated user.
    """
    import asyncio
    import json
    from starlette.responses import StreamingResponse
    from .notifications import notification_broadcaster

    queue = notification_broadcaster.subscribe(user.id)

    async def event_generator():
        try:
            # Initial verification ping
            yield f"event: connected\ndata: {json.dumps({'status': 'connected', 'user_id': str(user.id)})}\n\n"

            while True:
                try:
                    entry = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(entry)}\n\n"
                except asyncio.TimeoutError:
                    yield f": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            notification_broadcaster.unsubscribe(user.id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ─── Notification Rules (CRUD) ──────────────────────────────────────────────

@notification_router.get("/rules", response_model=StandardResponse)
async def list_rules(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Lists active notification rules. Requires subscription-tier feature access.
    """
    require_licensed_feature("settings", "notification_rules")

    stmt = select(NotificationRule).where(NotificationRule.is_deleted == False)
    if user.subsidiary_id:
        stmt = stmt.where(NotificationRule.subsidiary_id == user.subsidiary_id)

    result = await session.execute(stmt)
    rules = result.scalars().all()
    return success_response(rules)


@notification_router.post("/rules", response_model=StandardResponse)
async def create_rule(
    rule_in: NotificationRuleCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Creates a new notification rule. Enforces subscription level features (e.g. Email channel requires Pro+).
    """
    require_licensed_feature("settings", "notification_rules")

    if rule_in.channel == "EMAIL":
        # Extra licensing assertion for verification consistency
        require_licensed_feature("settings", "notification_rules")

    rule = NotificationRule(
        event_type=rule_in.event_type,
        channel=rule_in.channel,
        template_title=rule_in.template_title,
        template_body=rule_in.template_body,
        recipient_type=rule_in.recipient_type,
        recipient_target=rule_in.recipient_target,
        is_active=rule_in.is_active,
        subsidiary_id=user.subsidiary_id
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return success_response(rule)


@notification_router.put("/rules/{id}", response_model=StandardResponse)
async def update_rule(
    id: uuid.UUID,
    rule_in: NotificationRuleCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Updates an existing notification rule.
    """
    require_licensed_feature("settings", "notification_rules")

    stmt = select(NotificationRule).where(
        NotificationRule.id == id,
        NotificationRule.is_deleted == False
    )
    if user.subsidiary_id:
        stmt = stmt.where(NotificationRule.subsidiary_id == user.subsidiary_id)

    result = await session.execute(stmt)
    rule = result.scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="Notification rule not found")

    if rule_in.channel == "EMAIL":
        require_licensed_feature("settings", "notification_rules")

    rule.event_type = rule_in.event_type
    rule.channel = rule_in.channel
    rule.template_title = rule_in.template_title
    rule.template_body = rule_in.template_body
    rule.recipient_type = rule_in.recipient_type
    rule.recipient_target = rule_in.recipient_target
    rule.is_active = rule_in.is_active

    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return success_response(rule)


@notification_router.delete("/rules/{id}", response_model=StandardResponse)
async def delete_rule(
    id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Soft-deletes a notification rule.
    """
    require_licensed_feature("settings", "notification_rules")

    stmt = select(NotificationRule).where(
        NotificationRule.id == id,
        NotificationRule.is_deleted == False
    )
    if user.subsidiary_id:
        stmt = stmt.where(NotificationRule.subsidiary_id == user.subsidiary_id)

    result = await session.execute(stmt)
    rule = result.scalars().first()
    if not rule:
        raise HTTPException(status_code=404, detail="Notification rule not found")

    rule.is_deleted = True
    session.add(rule)
    await session.commit()
    return success_response({"detail": "Notification rule deleted"})

