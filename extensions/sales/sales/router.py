"""
Sales API Router.
Thin HTTP layer — uses proper schemas for input validation.
Every mutation is audit-logged for process transparency.
"""
import uuid
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from .models import Quotation, QuotationItem, QuotationStatus, SalesOrder
from .schemas import QuotationCreate, SalesOrderCreate
from .events import emit_order_confirmed
from core.responses import success_response, paginated_response
from core.database import get_async_session
from core.pagination import PaginationParams
from core.audit import AuditService
from core.middleware import current_user_id_context, current_user_name_context

router = APIRouter(prefix="/api/v1/sales", tags=["sales"])


def _actor_info() -> tuple[str | None, str]:
    return current_user_id_context.get(), current_user_name_context.get() or "system"


# --- Quotations ---

@router.get("/quotations")
async def get_quotations(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    count_stmt = select(func.count()).select_from(Quotation).where(Quotation.is_deleted == False)
    total = (await session.execute(count_stmt)).scalar() or 0
    stmt = (
        select(Quotation).where(Quotation.is_deleted == False)
        .offset(pagination.offset).limit(pagination.limit)
    )
    result = await session.execute(stmt)
    return paginated_response(data=result.scalars().all(), total=total, page=pagination.page, page_size=pagination.page_size)


@router.post("/quotations")
async def create_quotation(
    payload: QuotationCreate,
    session: AsyncSession = Depends(get_async_session)
):
    quotation = Quotation(
        customer_id=payload.customer_id, posting_date=payload.posting_date,
        valid_until=payload.valid_until, status=QuotationStatus.DRAFT
    )
    session.add(quotation)
    await session.flush()

    total = Decimal("0.0")
    for item_data in payload.items:
        amount = item_data.qty * item_data.rate
        item = QuotationItem(
            quotation_id=quotation.id, product_id=item_data.product_id,
            qty=item_data.qty, rate=item_data.rate, amount=amount
        )
        session.add(item)
        total += amount

    quotation.total_amount = total
    session.add(quotation)

    # Audit
    actor_id, actor_name = _actor_info()
    await AuditService.log_action(
        session=session, entity_type="sales.Quotation", entity_id=quotation.id,
        action="CREATE", module="sales",
        description=f"Created quotation for customer {payload.customer_id} — Total: {total}",
        actor_id=actor_id, actor_name=actor_name,
        changes={"action_data": {"customer_id": str(payload.customer_id), "items_count": len(payload.items), "total": str(total)}},
    )

    await session.commit()
    await session.refresh(quotation)
    return success_response(quotation)


@router.get("/quotations/{quotation_id}")
async def get_quotation(quotation_id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    quotation = await session.get(Quotation, quotation_id)
    if not quotation or quotation.is_deleted:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return success_response(quotation)


@router.post("/quotations/{quotation_id}/accept")
async def accept_quotation(quotation_id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    quotation = await session.get(Quotation, quotation_id)
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")

    old_status = quotation.status
    quotation.status = QuotationStatus.ACCEPTED
    session.add(quotation)

    # Audit: status transition with field change tracking
    actor_id, actor_name = _actor_info()
    await AuditService.log_action(
        session=session, entity_type="sales.Quotation", entity_id=quotation.id,
        action="STATUS_CHANGE", module="sales",
        description=f"Accepted quotation — Amount: {quotation.total_amount}",
        actor_id=actor_id, actor_name=actor_name,
        changes={"action_data": {"total_amount": str(quotation.total_amount)}},
        field_changes=[{"field": "status", "old": old_status, "new": QuotationStatus.ACCEPTED}],
    )

    await session.commit()
    return success_response(quotation)


# --- Sales Orders ---

@router.get("/orders")
async def get_orders(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    count_stmt = select(func.count()).select_from(SalesOrder).where(SalesOrder.is_deleted == False)
    total = (await session.execute(count_stmt)).scalar() or 0
    stmt = (
        select(SalesOrder).where(SalesOrder.is_deleted == False)
        .offset(pagination.offset).limit(pagination.limit)
    )
    result = await session.execute(stmt)
    return paginated_response(data=result.scalars().all(), total=total, page=pagination.page, page_size=pagination.page_size)


@router.post("/orders")
async def create_order(payload: SalesOrderCreate, session: AsyncSession = Depends(get_async_session)):
    order = SalesOrder(
        customer_id=payload.customer_id, total_amount=payload.total_amount,
        status="DRAFT", quotation_id=payload.quotation_id
    )
    session.add(order)
    await session.flush()

    actor_id, actor_name = _actor_info()
    await AuditService.log_action(
        session=session, entity_type="sales.SalesOrder", entity_id=order.id,
        action="CREATE", module="sales",
        description=f"Created sales order — Amount: {payload.total_amount}",
        actor_id=actor_id, actor_name=actor_name,
        changes={"action_data": {"customer_id": str(payload.customer_id), "total": str(payload.total_amount)}},
    )

    await session.commit()
    await session.refresh(order)
    return success_response(order)


@router.post("/orders/{order_id}/confirm")
async def confirm_order(order_id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    order = await session.get(SalesOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    old_status = order.status
    order.status = "CONFIRMED"
    session.add(order)

    actor_id, actor_name = _actor_info()
    await AuditService.log_action(
        session=session, entity_type="sales.SalesOrder", entity_id=order.id,
        action="CONFIRM", module="sales",
        description=f"Confirmed sales order — Amount: {order.total_amount}",
        actor_id=actor_id, actor_name=actor_name,
        changes={"action_data": {"total": str(order.total_amount), "customer_id": str(order.customer_id)}, "triggered_event": "ORDER_CONFIRMED"},
        field_changes=[{"field": "status", "old": old_status, "new": "CONFIRMED"}],
    )

    await session.commit()

    await emit_order_confirmed(
        order_id=str(order.id), total_amount=str(order.total_amount), customer_id=str(order.customer_id)
    )

    return success_response(order)
