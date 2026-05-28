import uuid
import logging
from decimal import Decimal
from sqlmodel import select

from core.events import event_bus, BaseEventPayload
from core.database import get_session_maker
from .models import SalesOrderLine

logger = logging.getLogger(__name__)


async def handle_order_shipped(payload: BaseEventPayload):
    """
    Subscribes to SELL_ORDER_SHIPPED.
    Updates Sales Order shipped quantities and transitions status.
    """
    order_id_str = payload.data.get("order_id")
    if not order_id_str:
        return

    order_id = uuid.UUID(order_id_str)
    session_maker = get_session_maker()

    async with session_maker() as session:
        from sqlalchemy.orm import selectinload
        from .models import SalesOrder
        stmt = (
            select(SalesOrder)
            .where(SalesOrder.id == order_id)
            .options(selectinload(SalesOrder.line_items))
            .with_for_update()
        )
        res = await session.execute(stmt)
        order = res.scalars().first()
        if not order:
            logger.error(f"[Sales] Order {order_id} not found on ship event")
            return

        shipped_items = payload.data.get("shipped_items", [])
        ship_map = {
            uuid.UUID(item["product_id"]): Decimal(str(item["qty"]))
            for item in shipped_items
        }

        fully_shipped = True
        for line in order.line_items:
            if line.product_id in ship_map:
                line.shipped_qty += ship_map[line.product_id]
                session.add(line)

            if line.shipped_qty < line.qty:
                fully_shipped = False

        order.status = "shipped" if fully_shipped else "partially_shipped"
        session.add(order)
        await session.commit()
        logger.info(f"[Sales] Updated Order {order_id} status to {order.status}")


async def handle_invoice_generated(payload: BaseEventPayload):
    """
    Subscribes to SELL_INVOICE_GENERATED.
    Updates Sales Order status to invoiced and updates invoiced_qty.
    """
    order_id_str = payload.data.get("order_id")
    if not order_id_str:
        return

    order_id = uuid.UUID(order_id_str)
    session_maker = get_session_maker()

    async with session_maker() as session:
        from sqlalchemy.orm import selectinload
        from .models import SalesOrder
        stmt = (
            select(SalesOrder)
            .where(SalesOrder.id == order_id)
            .options(selectinload(SalesOrder.line_items))
            .with_for_update()
        )
        res = await session.execute(stmt)
        order = res.scalars().first()
        if not order:
            logger.error(f"[Sales] Order {order_id} not found on invoice event")
            return

        # For this standard flow, invoice covers the whole order
        for line in order.line_items:
            line.invoiced_qty = line.qty
            session.add(line)

        order.status = "invoiced"
        session.add(order)
        await session.commit()
        logger.info(f"[Sales] Updated Order {order_id} status to invoiced")


async def handle_payment_collected(payload: BaseEventPayload):
    """
    Subscribes to SELL_PAYMENT_COLLECTED.
    Transitions Sales Order to completed if fully paid.
    """
    invoice_id_str = payload.data.get("invoice_id")
    if not invoice_id_str:
        return

    invoice_id = uuid.UUID(invoice_id_str)
    session_maker = get_session_maker()

    async with session_maker() as session:
        # Load the invoice to check status and order link
        # To avoid circular imports, load dynamically
        from extensions.finance.finance.models import FinanceInvoice
        stmt = select(FinanceInvoice).where(FinanceInvoice.id == invoice_id)
        res = await session.execute(stmt)
        invoice = res.scalars().first()
        if not invoice:
            logger.error(f"[Sales] Invoice {invoice_id} not found on payment event")
            return

        order_id = invoice.order_id
        if not order_id:
            return

        from .services import order_repo
        order = await order_repo.get_with_lock(session, order_id)
        if not order:
            return

        if invoice.status == "paid":
            order.status = "completed"
            session.add(order)
            await session.commit()
            logger.info(f"[Sales] Completed Order {order_id} on invoice payment")


def register_event_handlers():
    event_bus.subscribe("SELL_ORDER_SHIPPED", handle_order_shipped)
    event_bus.subscribe("SELL_INVOICE_GENERATED", handle_invoice_generated)
    event_bus.subscribe("SELL_PAYMENT_COLLECTED", handle_payment_collected)
    logger.info("[Sales] Event handlers registered successfully")
