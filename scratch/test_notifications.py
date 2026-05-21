import os
import sys
import asyncio
import uuid
from datetime import datetime, timezone
from sqlmodel import SQLModel, select

# Set up DATABASE_URL for sqlite in-memory database
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SQL_ECHO"] = "false"

# Add core kernel module to path to run the test script
sys.path.insert(0, "/Users/bvk/BVK_Workspace/BES/bes-backend/core")

from core.database import get_engine, get_session_maker
from core.models import User, Role
from core.events import event_bus, BaseEventPayload
from core.licensing import PERMISSIONS_SCHEMA
from core.notifications import Notification, NotificationRule, NotificationService, notification_broadcaster


async def run_tests():
    print("=== Starting Core Notification Service Tests ===")
    
    # 1. Initialize DB and Create Tables
    engine = get_engine()
    async with engine.begin() as conn:
        # Create all tables (User, Role, NotificationRule, Notification, etc.)
        await conn.run_sync(SQLModel.metadata.create_all)
    
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        # 2. Seed Test User and Role
        admin_role = Role(name="admin", permissions={})
        session.add(admin_role)
        await session.commit()
        await session.refresh(admin_role)
        
        test_user = User(
            username="test_user",
            email="test_user@bes.com",
            hashed_password="mock_password_hash",
            full_name="Test User",
            is_active=True,
            role_id=admin_role.id
        )
        session.add(test_user)
        await session.commit()
        await session.refresh(test_user)
        user_id = test_user.id
        role_id = admin_role.id
        
    print("Database seeded with test user and role.")

    # Test case 1: Jinja2 rendering verification
    print("Test 1: Jinja2 template rendering...", end=" ")
    title_tpl = "Order #{{ order_id }} Status"
    body_tpl = "Hi {{ user_name }}, your order for ${{ amount }} is now {{ status }}."
    context = {"order_id": 1024, "user_name": "Alice", "amount": "250.00", "status": "completed"}
    
    rendered_title = NotificationService._render_text(title_tpl, context)
    rendered_body = NotificationService._render_text(body_tpl, context)
    
    assert rendered_title == "Order #1024 Status"
    assert rendered_body == "Hi Alice, your order for $250.00 is now completed."
    print("PASSED")

    # Test case 2: SSE subscription and broadcaster queueing
    print("Test 2: Broadcaster subscription queue...", end=" ")
    queue = notification_broadcaster.subscribe(user_id)
    assert queue.qsize() == 0
    
    mock_payload = {"id": "test-uuid", "title": "Hello", "body": "World"}
    await notification_broadcaster.send_to_user(user_id, mock_payload)
    assert queue.qsize() == 1
    
    queued_item = await queue.get()
    assert queued_item["title"] == "Hello"
    
    notification_broadcaster.unsubscribe(user_id, queue)
    print("PASSED")

    # Test case 3: Event-triggered In-App notifications
    print("Test 3: Event-triggered In-App rule flow...", end=" ")
    
    # Enable notification_rules in mock permissions schema to simulate a licensed environment
    original_schema = PERMISSIONS_SCHEMA.copy()
    PERMISSIONS_SCHEMA.clear()
    PERMISSIONS_SCHEMA.update({
        "settings": {
            "notification_rules": {"read": True, "write": True, "delete": True}
        }
    })
    
    try:
        # Subscribe user to receive real-time updates
        user_queue = notification_broadcaster.subscribe(user_id)
        
        async with session_maker() as session:
            # Create a rule targeting the user on a SALES_ORDER_COMPLETED event
            rule = NotificationRule(
                event_type="SALES_ORDER_COMPLETED",
                channel="IN_APP",
                template_title="Order #{{ order_id }} Shipped",
                template_body="Good news! Your order of ${{ amount }} has shipped.",
                recipient_type="USER",
                recipient_target=str(user_id),
                is_active=True
            )
            session.add(rule)
            await session.commit()
            
        # Emit the event via event_bus
        event = BaseEventPayload(
            emitter_module="sales",
            event_type="SALES_ORDER_COMPLETED",
            data={"order_id": "999888", "amount": "450.00"}
        )
        await event_bus.emit(event)
        
        # Wait a small moment for async task delivery
        await asyncio.sleep(0.2)
        
        # Assert database entry was created
        async with session_maker() as session:
            stmt = select(Notification).where(Notification.user_id == user_id)
            result = await session.execute(stmt)
            notifs = result.scalars().all()
            
            assert len(notifs) == 1
            assert notifs[0].title == "Order #999888 Shipped"
            assert notifs[0].body == "Good news! Your order of $450.00 has shipped."
            assert notifs[0].status == "SENT"
            
        # Assert SSE broadcoast received
        assert user_queue.qsize() == 1
        sse_item = await user_queue.get()
        assert sse_item["title"] == "Order #999888 Shipped"
        
        notification_broadcaster.unsubscribe(user_id, user_queue)
        print("PASSED")

        # Test case 4: Subscription Tier Lockout (EMAIL channel gated on Basic plan)
        print("Test 4: EMAIL channel licensing lock (Basic Plan exclusion)...", end=" ")
        
        # Scenario A: basic plan setup (no settings:notification_rules feature)
        PERMISSIONS_SCHEMA.clear() # Basic has no settings permissions
        
        async with session_maker() as session:
            # Create an EMAIL notification rule
            email_rule = NotificationRule(
                event_type="SALES_ORDER_COMPLETED",
                channel="EMAIL",
                template_title="Email Notification",
                template_body="This is an email.",
                recipient_type="USER",
                recipient_target=str(user_id),
                is_active=True
            )
            session.add(email_rule)
            await session.commit()
            
        # Emit another event
        event2 = BaseEventPayload(
            emitter_module="sales",
            event_type="SALES_ORDER_COMPLETED",
            data={"order_id": "email-test"}
        )
        await event_bus.emit(event2)
        await asyncio.sleep(0.2)
        
        # Since Basic plan does not license settings:notification_rules,
        # the email rule must be blocked and skipped. Let's assert NO email notification is created.
        async with session_maker() as session:
            stmt = select(Notification).where(
                Notification.channel == "EMAIL"
            )
            result = await session.execute(stmt)
            email_notifs = result.scalars().all()
            assert len(email_notifs) == 0, "Email notification should have been bypassed/blocked by license check"
            
        print("PASSED (Email skipped on basic)")

        # Scenario B: pro plan setup (settings:notification_rules feature active)
        print("Test 5: EMAIL channel execution (Pro/Premium Plan validation)...", end=" ")
        PERMISSIONS_SCHEMA.clear()
        PERMISSIONS_SCHEMA.update({
            "settings": {
                "notification_rules": {"read": True, "write": True, "delete": True}
            }
        })
        
        # We must create a new BaseEventPayload because reuse leads to duplicate UUID key errors
        event3 = BaseEventPayload(
            emitter_module="sales",
            event_type="SALES_ORDER_COMPLETED",
            data={"order_id": "email-test-pro"}
        )
        await event_bus.emit(event3)
        await asyncio.sleep(0.2)
        
        # Verify that under Pro plan, the email notification rule executed and logged/saved properly
        async with session_maker() as session:
            stmt = select(Notification).where(
                Notification.channel == "EMAIL"
            )
            result = await session.execute(stmt)
            email_notifs = result.scalars().all()
            assert len(email_notifs) == 1
            assert email_notifs[0].title == "Email Notification"
            assert email_notifs[0].status == "SENT"
            
        print("PASSED (Email sent on pro)")

    finally:
        # Restore original PERMISSIONS_SCHEMA
        PERMISSIONS_SCHEMA.clear()
        PERMISSIONS_SCHEMA.update(original_schema)

    print("\n=== All Core Notification Tests PASSED! ===")


if __name__ == "__main__":
    asyncio.run(run_tests())
