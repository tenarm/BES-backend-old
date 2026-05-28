import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from pydantic import BaseModel
from ..database import get_async_session
from ..models import User
from ..auth import get_current_user
from ..pagination import PaginationParams
from ..responses import StandardResponse, success_response, paginated_response
from ..licensing import require_licensed_feature
from ..notifications import Notification, NotificationRule

logger = logging.getLogger(__name__)

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
    from ..notifications import notification_broadcaster

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
        # Email delivery requires a Pro+ subscription ("notification_rules" is a Pro feature).
        # The check at the top of this function already enforces this, but the explicit
        # comment here documents the intent for future sub-feature granularity.
        require_licensed_feature("settings", "email_notifications")

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
        require_licensed_feature("settings", "email_notifications")

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
