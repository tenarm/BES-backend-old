import pytest
import uuid
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.models import User
from core.events import event_bus, BaseEventPayload
from core.notifications import NotificationRule, Notification, notification_broadcaster
from core.auth import get_password_hash


@pytest.mark.asyncio
async def test_in_app_notification_trigger(client: AsyncClient, db_session: AsyncSession):
    """Verifies that emitting an event matching a NotificationRule generates the correct notification in the database."""
    # 1. Create a User in the database
    target_user = User(
        id=uuid.uuid4(),
        username="notifyee",
        email="notifyee@example.com",
        hashed_password=get_password_hash("secure123"),
        is_active=True,
        is_superuser=False,
        role_id=None
    )
    db_session.add(target_user)
    await db_session.commit()
    await db_session.refresh(target_user)

    # 2. Create a NotificationRule matching event type "TEST_NOTIF_EVENT"
    notif_rule = NotificationRule(
        id=uuid.uuid4(),
        event_type="TEST_NOTIF_EVENT",
        channel="IN_APP",
        template_title="New Notification for {{ username }}",
        template_body="The action {{ action_name }} succeeded.",
        recipient_type="USER",
        recipient_target=str(target_user.id),
        is_active=True
    )
    db_session.add(notif_rule)
    await db_session.commit()

    # 3. Emit the matching event payload
    event = BaseEventPayload(
        emitter_module="test_module",
        event_type="TEST_NOTIF_EVENT",
        data={
            "username": "notifyee",
            "action_name": "Deploying Gold Standards"
        }
    )
    await event_bus.emit(event)

    # 4. Give the background task a moment to process and save the notification
    await asyncio.sleep(0.2)

    # 5. Query the database to verify the notification was created
    stmt = select(Notification).where(Notification.user_id == target_user.id)
    result = await db_session.execute(stmt)
    notifications = result.scalars().all()

    assert len(notifications) == 1
    notif = notifications[0]
    assert notif.title == "New Notification for notifyee"
    assert notif.body == "The action Deploying Gold Standards succeeded."
    assert notif.channel == "IN_APP"
    assert notif.status in ("SENT", "PENDING")


@pytest.mark.asyncio
async def test_notification_sse_stream(client: AsyncClient, db_session: AsyncSession):
    """Verifies that in-app notifications are broadcast in real-time over the user's active SSE queue."""
    # 1. Create a user
    target_user = User(
        id=uuid.uuid4(),
        username="sse_user",
        email="sse@example.com",
        hashed_password=get_password_hash("ssepass123"),
        is_active=True,
        is_superuser=False,
        role_id=None
    )
    db_session.add(target_user)
    await db_session.commit()
    await db_session.refresh(target_user)

    # 2. Subscribe to the SSE broadcaster for this user
    user_queue = notification_broadcaster.subscribe(target_user.id)

    try:
        # 3. Create a pending notification for this user
        notif = Notification(
            id=uuid.uuid4(),
            user_id=target_user.id,
            title="SSE Broadcast Alert",
            body="This should go to the subscriber queue.",
            channel="IN_APP",
            status="PENDING"
        )
        db_session.add(notif)
        await db_session.commit()

        # 4. Trigger delivery
        from core.notifications import NotificationService
        await NotificationService.deliver_pending_notifications()

        # 5. Read the notification payload from the queue with a timeout
        payload = await asyncio.wait_for(user_queue.get(), timeout=1.0)

        # 6. Verify payload contents
        assert payload["id"] == str(notif.id)
        assert payload["title"] == "SSE Broadcast Alert"
        assert payload["body"] == "This should go to the subscriber queue."
        assert payload["channel"] == "IN_APP"
        assert payload["status"] == "SENT"

    finally:
        # Always clean up the subscription
        notification_broadcaster.unsubscribe(target_user.id, user_queue)

