import asyncio
import sys
from sqlmodel import SQLModel, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Set database URL
DATABASE_URL = "sqlite+aiosqlite:////Users/bvk/BVK_Workspace/BES/bes-backend/instances/msme_basic/data/msme_basic.db"

async def main():
    # Setup path overrides
    sys.path.insert(0, "/Users/bvk/BVK_Workspace/BES/bes-backend/core")
    sys.path.insert(0, "/Users/bvk/BVK_Workspace/BES/bes-backend/extensions/sales")
    sys.path.insert(0, "/Users/bvk/BVK_Workspace/BES/bes-backend/extensions/inventory")
    sys.path.insert(0, "/Users/bvk/BVK_Workspace/BES/bes-backend/extensions/finance")
    sys.path.insert(0, "/Users/bvk/BVK_Workspace/BES/bes-backend/extensions/settings")

    from core.models import User, Role, Customer, Product
    from core.sequences import SequenceService
    from core.notifications import NotificationRule

    engine = create_async_engine(DATABASE_URL, echo=True)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # Seed
    session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        # Seed sequences
        sequence_service = SequenceService()
        await sequence_service.ensure_sequence(session, "sales_quotation", "QT", pattern="{PREFIX}-{YYYY}{SEQ:05d}")
        await sequence_service.ensure_sequence(session, "sales_order", "SO", pattern="{PREFIX}-{YYYY}{SEQ:05d}")
        await sequence_service.ensure_sequence(session, "inventory_shipment", "SH", pattern="{PREFIX}-{YYYY}{SEQ:05d}")
        await sequence_service.ensure_sequence(session, "finance_invoice", "INV", pattern="{PREFIX}-{YYYY}{SEQ:05d}")
        await sequence_service.ensure_sequence(session, "finance_payment", "PAY", pattern="{PREFIX}-{YYYY}{SEQ:05d}")

        # Seed admin notification rules
        user_stmt = select(User).where(User.username == "admin")
        user_res = await session.execute(user_stmt)
        admin_user = user_res.scalars().first()
        
        if admin_user:
            admin_id_str = str(admin_user.id)
            rules_to_seed = [
                {
                    "event_type": "SELL_ORDER_CONFIRMED",
                    "channel": "IN_APP",
                    "template_title": "Sales Order Confirmed",
                    "template_body": "Sales Order {{ order_id }} has been confirmed and is ready for shipment.",
                    "recipient_type": "USER",
                    "recipient_target": admin_id_str
                },
                {
                    "event_type": "SELL_ORDER_SHIPPED",
                    "channel": "IN_APP",
                    "template_title": "Order Shipped",
                    "template_body": "Shipment {{ shipment_id }} has been dispatched for Order {{ order_id }}.",
                    "recipient_type": "USER",
                    "recipient_target": admin_id_str
                },
                {
                    "event_type": "SELL_INVOICE_GENERATED",
                    "channel": "IN_APP",
                    "template_title": "Invoice Generated",
                    "template_body": "Invoice {{ invoice_id }} has been generated for Order {{ order_id }}.",
                    "recipient_type": "USER",
                    "recipient_target": admin_id_str
                }
            ]

            for r_data in rules_to_seed:
                r_stmt = select(NotificationRule).where(NotificationRule.event_type == r_data["event_type"])
                r_res = await session.execute(r_stmt)
                if not r_res.scalars().first():
                    rule = NotificationRule(**r_data)
                    session.add(rule)

        await session.commit()
    print("Database seeding completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
