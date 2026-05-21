import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Any, Dict, List
from jinja2 import Template
from sqlmodel import SQLModel, Field, select
from sqlalchemy import Column, JSON

from core.models import BESBase, User
from core.licensing import is_feature_licensed

logger = logging.getLogger(__name__)

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

# ─── Database Models ────────────────────────────────────────────────────────

class NotificationRule(BESBase, table=True):
    """
    Tenant-scoped rule defining when and how to generate notifications.
    Triggered when event_type matches an emitted event.
    """
    __tablename__ = "notification_rules"

    event_type: str = Field(index=True)  # e.g., "SALES_ORDER_COMPLETED"
    channel: str = Field(default="IN_APP", index=True)  # "IN_APP" | "EMAIL"
    
    # Template strings parsed with Jinja2 using event payload data
    template_title: str = Field(default="")
    template_body: str = Field(default="")
    
    # Recipient routing rules
    recipient_type: str = Field(default="USER")  # "USER" | "ROLE" | "PAYLOAD_FIELD"
    recipient_target: str = Field()  # User UUID, Role UUID, or event payload dictionary path (e.g. "customer_email")
    
    is_active: bool = Field(default=True)


class Notification(BESBase, table=True):
    """
    Log of individual sent or pending notifications.
    """
    __tablename__ = "notifications"

    user_id: Optional[uuid.UUID] = Field(default=None, foreign_key="users.id", index=True)
    email_address: Optional[str] = Field(default=None, index=True)
    
    title: str = Field()
    body: str = Field()
    channel: str = Field()  # "IN_APP" | "EMAIL"
    status: str = Field(default="PENDING", index=True)  # "PENDING" | "SENT" | "READ" | "FAILED"
    
    read_at: Optional[datetime] = Field(default=None)
    error_message: Optional[str] = Field(default=None)


# ─── SSE Notification Broadcaster ──────────────────────────────────────────

class NotificationBroadcaster:
    """
    Per-user in-memory subscription queues for real-time notification push over SSE.
    """
    def __init__(self):
        self._subscribers: Dict[uuid.UUID, set[asyncio.Queue]] = {}

    def subscribe(self, user_id: uuid.UUID) -> asyncio.Queue:
        if user_id not in self._subscribers:
            self._subscribers[user_id] = set()
        q = asyncio.Queue(maxsize=256)
        self._subscribers[user_id].add(q)
        logger.debug(f"User {user_id} subscribed to live notifications. Queue count: {len(self._subscribers[user_id])}")
        return q

    def unsubscribe(self, user_id: uuid.UUID, q: asyncio.Queue):
        if user_id in self._subscribers:
            self._subscribers[user_id].discard(q)
            if not self._subscribers[user_id]:
                del self._subscribers[user_id]
            logger.debug(f"User {user_id} unsubscribed from live notifications.")

    async def send_to_user(self, user_id: uuid.UUID, data: dict):
        if user_id not in self._subscribers:
            return
        
        dead = []
        for q in list(self._subscribers[user_id]):
            try:
                q.put_nowait(data)
            except asyncio.QueueFull:
                dead.append(q)
                
        for q in dead:
            self._subscribers[user_id].discard(q)
            
        if user_id in self._subscribers and not self._subscribers[user_id]:
            del self._subscribers[user_id]


notification_broadcaster = NotificationBroadcaster()


# ─── Notification Service ───────────────────────────────────────────────────

class NotificationService:
    """
    Business logic and delivery mechanisms for core notifications.
    """

    @staticmethod
    def _render_text(template_str: str, context: dict) -> str:
        try:
            return Template(template_str).render(**context)
        except Exception as e:
            logger.error(f"Failed to render notification template: {e}")
            return template_str

    @staticmethod
    async def process_event_notifications(payload: Any):
        """
        Triggered dynamically when any event is emitted. Finds matching active rules,
        renders templates, and delivers notifications in a separate session.
        """
        from core.database import get_session_maker
        from core.rbac import elevate_context
        
        event_type = payload.event_type
        event_data = payload.data
        sub_id = getattr(payload, "subsidiary_id", None)
        
        session_maker = get_session_maker()
        async with session_maker() as session:
            # Query rules matching the event type
            stmt = select(NotificationRule).where(
                NotificationRule.event_type == event_type,
                NotificationRule.is_active == True
            )
            result = await session.execute(stmt)
            rules = result.scalars().all()
            
            if not rules:
                return

            for rule in rules:
                # 1. Enforce licensing: EMAIL requires Pro/Premium plan (notification_rules enabled)
                if rule.channel == "EMAIL":
                    # Settings module is checked for notification_rules feature license
                    if not is_feature_licensed("settings", "notification_rules"):
                        logger.warning(
                            f"Subscription Bypass Blocked: "
                            f"Bypassing rule {rule.id} (EMAIL channel requires Pro/Premium subscription)"
                        )
                        continue

                # 2. Render Template
                title = NotificationService._render_text(rule.template_title, event_data)
                body = NotificationService._render_text(rule.template_body, event_data)
                
                # 3. Resolve Recipients
                recipients = await NotificationService._resolve_recipients(session, rule, event_data)
                
                for rec in recipients:
                    notif = Notification(
                        subsidiary_id=sub_id or rule.subsidiary_id,
                        user_id=rec.get("user_id"),
                        email_address=rec.get("email_address"),
                        title=title,
                        body=body,
                        channel=rule.channel,
                        status="PENDING"
                    )
                    session.add(notif)
            
            await session.commit()
            
            # 4. Trigger asynchronous delivery of pending entries
            asyncio.create_task(NotificationService.deliver_pending_notifications())

    @staticmethod
    async def _resolve_recipients(session: Any, rule: NotificationRule, event_data: dict) -> List[Dict[str, Any]]:
        """
        Resolves recipients target configured in the rule based on type.
        """
        recipients = []

        if rule.recipient_type == "USER":
            try:
                user_uuid = uuid.UUID(rule.recipient_target)
                user = await session.get(User, user_uuid)
                if user and user.is_active:
                    recipients.append({"user_id": user.id, "email_address": user.email})
            except ValueError:
                logger.error(f"Invalid user UUID: {rule.recipient_target}")

        elif rule.recipient_type == "ROLE":
            try:
                role_uuid = uuid.UUID(rule.recipient_target)
                stmt = select(User).where(User.role_id == role_uuid, User.is_active == True)
                result = await session.execute(stmt)
                users = result.scalars().all()
                for user in users:
                    recipients.append({"user_id": user.id, "email_address": user.email})
            except ValueError:
                logger.error(f"Invalid role UUID: {rule.recipient_target}")

        elif rule.recipient_type == "PAYLOAD_FIELD":
            # Target resides dynamically inside event payload (e.g. "customer_email" or "salesperson_id")
            val = event_data.get(rule.recipient_target)
            if val:
                # Check if it is a user ID
                try:
                    user_uuid = uuid.UUID(str(val))
                    user = await session.get(User, user_uuid)
                    if user and user.is_active:
                        recipients.append({"user_id": user.id, "email_address": user.email})
                except ValueError:
                    # Treat as raw email address if it contains '@'
                    if isinstance(val, str) and "@" in val:
                        recipients.append({"user_id": None, "email_address": val})

        return recipients

    @staticmethod
    async def deliver_pending_notifications():
        """
        Background task to process and deliver pending notifications.
        """
        from core.database import get_session_maker
        
        session_maker = get_session_maker()
        async with session_maker() as session:
            stmt = select(Notification).where(Notification.status == "PENDING")
            result = await session.execute(stmt)
            pending = result.scalars().all()
            
            if not pending:
                return
                
            for notif in pending:
                try:
                    if notif.channel == "IN_APP":
                        await NotificationService._dispatch_in_app(session, notif)
                    elif notif.channel == "EMAIL":
                        await NotificationService._dispatch_email(notif)
                    notif.status = "SENT"
                except Exception as e:
                    logger.error(f"Failed to deliver notification {notif.id}: {e}")
                    notif.status = "FAILED"
                    notif.error_message = str(e)
            
            await session.commit()

    @staticmethod
    async def _dispatch_in_app(session: Any, notif: Notification):
        """
        Delivers notifications to user queues for real-time SSE broadcasts.
        """
        if not notif.user_id:
            raise ValueError("In-app notification requires a target user_id")
            
        # Push to SSE broadcaster
        payload = {
            "id": str(notif.id),
            "created_at": notif.created_at.isoformat() if notif.created_at else utc_now().isoformat(),
            "title": notif.title,
            "body": notif.body,
            "channel": notif.channel,
            "status": "SENT"
        }
        await notification_broadcaster.send_to_user(notif.user_id, payload)

    @staticmethod
    async def _dispatch_email(notif: Notification):
        """
        SMTP delivery mechanism (logs mock payload in development).
        """
        target = notif.email_address
        if not target and notif.user_id:
            # Fallback will look up email if needed, but resolved recipients are pre-filled
            raise ValueError("Email notification requires an email address")
            
        logger.info(
            f"[MOCK SMTP SEND] To: {target} | Subject: {notif.title} | Body: {notif.body}"
        )
