import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Sequence
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.repository import BaseRepository
from core.sequences import SequenceService
from core.events import event_bus, BaseEventPayload
from core.exceptions import EntityNotFoundError, ValidationError, StateTransitionError
from core.models.master_data import Customer
from .models import SalesQuotation, SalesQuotationLine, SalesOrder, SalesOrderLine
from .schemas import SalesQuotationCreate, SalesOrderCreate


class QuotationRepository(BaseRepository[SalesQuotation]):
    def __init__(self):
        super().__init__(SalesQuotation)


class OrderRepository(BaseRepository[SalesOrder]):
    def __init__(self):
        super().__init__(SalesOrder)


quotation_repo = QuotationRepository()
order_repo = OrderRepository()


class QuotationService:
    def __init__(self):
        self.sequence_service = SequenceService()

    async def get_quotation(self, session: AsyncSession, quotation_id: uuid.UUID) -> Optional[SalesQuotation]:
        return await quotation_repo.get(session, quotation_id)

    async def get_all_quotations(self, session: AsyncSession, skip: int = 0, limit: int = 100) -> Sequence[SalesQuotation]:
        return await quotation_repo.get_all(session, skip=skip, limit=limit)

    async def create_quotation(self, session: AsyncSession, obj_in: SalesQuotationCreate) -> SalesQuotation:
        ref = await self.sequence_service.next_number(session, "sales_quotation")

        subtotal = Decimal("0.0")
        tax_amount = Decimal("0.0")
        line_items = []

        for line in obj_in.line_items:
            qty = Decimal(str(line.qty))
            unit_price = Decimal(str(line.unit_price))
            discount = Decimal(str(line.discount_amount))
            tax_rate = Decimal(str(line.tax_rate))

            line_total = (qty * unit_price) - discount
            line_total = line_total.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

            line_tax = line_total * tax_rate
            line_tax = line_tax.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

            subtotal += line_total
            tax_amount += line_tax

            db_line = SalesQuotationLine(
                product_id=line.product_id,
                qty=qty,
                unit_price=unit_price,
                discount_amount=discount,
                tax_rate=tax_rate,
                line_total=line_total
            )
            line_items.append(db_line)

        total_amount = subtotal + tax_amount
        total_amount = total_amount.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

        quotation = SalesQuotation(
            ref_number=ref,
            customer_id=obj_in.customer_id,
            valid_until=obj_in.valid_until,
            status="draft",
            subtotal=subtotal,
            tax_amount=tax_amount,
            total_amount=total_amount,
            line_items=line_items
        )

        quotation = await quotation_repo.create(session, quotation)

        event_payload = BaseEventPayload(
            emitter_module="sales",
            event_type="SELL_QUOTE_CREATED",
            data={
                "quotation_id": str(quotation.id),
                "customer_id": str(quotation.customer_id),
                "total_amount": str(quotation.total_amount)
            }
        )

        await session.commit()
        await event_bus.emit(event_payload)
        return quotation


class SalesOrderService:
    def __init__(self):
        self.sequence_service = SequenceService()

    async def get_order(self, session: AsyncSession, order_id: uuid.UUID) -> Optional[SalesOrder]:
        return await order_repo.get(session, order_id)

    async def get_all_orders(self, session: AsyncSession, skip: int = 0, limit: int = 100) -> Sequence[SalesOrder]:
        return await order_repo.get_all(session, skip=skip, limit=limit)

    async def create_order(self, session: AsyncSession, obj_in: SalesOrderCreate) -> SalesOrder:
        ref = await self.sequence_service.next_number(session, "sales_order")

        subtotal = Decimal("0.0")
        tax_amount = Decimal("0.0")
        line_items = []

        for line in obj_in.line_items:
            qty = Decimal(str(line.qty))
            unit_price = Decimal(str(line.unit_price))
            discount = Decimal(str(line.discount_amount))
            tax_rate = Decimal(str(line.tax_rate))

            line_total = (qty * unit_price) - discount
            line_total = line_total.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

            line_tax = line_total * tax_rate
            line_tax = line_tax.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

            subtotal += line_total
            tax_amount += line_tax

            db_line = SalesOrderLine(
                product_id=line.product_id,
                qty=qty,
                shipped_qty=Decimal("0.0"),
                invoiced_qty=Decimal("0.0"),
                unit_price=unit_price,
                discount_amount=discount,
                tax_rate=tax_rate,
                line_total=line_total
            )
            line_items.append(db_line)

        total_amount = subtotal + tax_amount
        total_amount = total_amount.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

        stmt = select(Customer).where(Customer.id == obj_in.customer_id)
        result = await session.execute(stmt)
        customer = result.scalars().first()
        if not customer:
            raise EntityNotFoundError("Customer", str(obj_in.customer_id))

        credit_warning = False
        if customer.credit_limit > Decimal("0.0"):
            available_credit = customer.credit_limit - customer.outstanding_balance
            if total_amount > available_credit:
                credit_warning = True

        order = SalesOrder(
            ref_number=ref,
            customer_id=obj_in.customer_id,
            quotation_id=obj_in.quotation_id,
            payment_terms=obj_in.payment_terms,
            status="draft",
            credit_warning=credit_warning,
            subtotal=subtotal,
            tax_amount=tax_amount,
            total_amount=total_amount,
            line_items=line_items
        )

        if obj_in.quotation_id:
            quotation = await quotation_repo.get(session, obj_in.quotation_id)
            if quotation:
                quotation.status = "won"
                session.add(quotation)

        order = await order_repo.create(session, order)
        await session.commit()
        return order

    async def confirm_order(self, session: AsyncSession, order_id: uuid.UUID) -> SalesOrder:
        from sqlalchemy.orm import selectinload
        stmt = (
            select(SalesOrder)
            .where(SalesOrder.id == order_id)
            .options(selectinload(SalesOrder.line_items))
            .with_for_update()
        )
        res = await session.execute(stmt)
        order = res.scalars().first()
        if not order:
            raise EntityNotFoundError("SalesOrder", str(order_id))

        if order.status != "draft":
            raise StateTransitionError("SalesOrder", order.status, "confirmed")

        order.status = "confirmed"
        session.add(order)

        event_payload = BaseEventPayload(
            emitter_module="sales",
            event_type="SELL_ORDER_CONFIRMED",
            data={
                "order_id": str(order.id),
                "customer_id": str(order.customer_id),
                "total_amount": str(order.total_amount),
                "line_items": [
                    {
                        "product_id": str(line.product_id),
                        "qty": str(line.qty),
                        "unit_price": str(line.unit_price)
                    }
                    for line in order.line_items
                ]
            }
        )

        await session.commit()
        await event_bus.emit(event_payload)
        return order

    async def cancel_order(self, session: AsyncSession, order_id: uuid.UUID) -> SalesOrder:
        order = await order_repo.get_with_lock(session, order_id)
        if not order:
            raise EntityNotFoundError("SalesOrder", str(order_id))

        if order.status not in ("draft", "confirmed"):
            raise StateTransitionError("SalesOrder", order.status, "cancelled")

        old_status = order.status
        order.status = "cancelled"
        session.add(order)

        event_payload = BaseEventPayload(
            emitter_module="sales",
            event_type="SELL_ORDER_CANCELLED",
            data={
                "order_id": str(order.id),
                "customer_id": str(order.customer_id),
                "old_status": old_status
            }
        )

        await session.commit()
        await event_bus.emit(event_payload)
        return order

    async def clone_order(self, session: AsyncSession, order_id: uuid.UUID) -> SalesOrder:
        from sqlalchemy.orm import selectinload
        stmt = (
            select(SalesOrder)
            .where(SalesOrder.id == order_id)
            .options(selectinload(SalesOrder.line_items))
        )
        res = await session.execute(stmt)
        order = res.scalars().first()
        if not order:
            raise EntityNotFoundError("SalesOrder", str(order_id))

        ref = await self.sequence_service.next_number(session, "sales_order")

        cloned_lines = []
        for line in order.line_items:
            db_line = SalesOrderLine(
                product_id=line.product_id,
                qty=line.qty,
                shipped_qty=Decimal("0.0"),
                invoiced_qty=Decimal("0.0"),
                unit_price=line.unit_price,
                discount_amount=line.discount_amount,
                tax_rate=line.tax_rate,
                line_total=line.line_total
            )
            cloned_lines.append(db_line)

        cloned_order = SalesOrder(
            ref_number=ref,
            customer_id=order.customer_id,
            payment_terms=order.payment_terms,
            status="draft",
            credit_warning=order.credit_warning,
            cloned_from_id=order.id,
            subtotal=order.subtotal,
            tax_amount=order.tax_amount,
            total_amount=order.total_amount,
            line_items=cloned_lines
        )

        cloned_order = await order_repo.create(session, cloned_order)
        await session.commit()
        return cloned_order
