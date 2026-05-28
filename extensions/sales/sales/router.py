import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from core.database import get_async_session
from core.responses import success_response, paginated_response
from core.pagination import PaginationParams
from core.licensing import require_licensed_feature
from core.rbac import require_permission
from core.exceptions import (
    ValidationError, EntityNotFoundError, StateTransitionError
)

from .schemas import SalesQuotationCreate, SalesOrderCreate
from .services import QuotationService, SalesOrderService
from .models import SalesQuotation, SalesOrder

router = APIRouter(prefix="/api/v1/sales", tags=["Sales"])
quotation_service = QuotationService()
order_service = SalesOrderService()


# --- Quotation Endpoints ---

@router.post("/quotations", dependencies=[Depends(require_permission("sales:quotations:write"))])
async def create_quotation(
    data: SalesQuotationCreate,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "quotations")
    try:
        quote = await quotation_service.create_quotation(session, data)
        return success_response(data=quote)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/quotations", dependencies=[Depends(require_permission("sales:quotations:read"))])
async def list_quotations(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "quotations")
    total_stmt = select(func.count()).select_from(SalesQuotation).where(SalesQuotation.is_deleted == False)
    total = (await session.execute(total_stmt)).scalar() or 0

    items = await quotation_service.get_all_quotations(session, skip=pagination.offset, limit=pagination.limit)
    return paginated_response(data=items, total=total, page=pagination.page, page_size=pagination.page_size)


@router.get("/quotations/{id}", dependencies=[Depends(require_permission("sales:quotations:read"))])
async def get_quotation(id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("sales", "quotations")
    quote = await quotation_service.get_quotation(session, id)
    if not quote:
        raise HTTPException(status_code=404, detail=f"Quotation with ID {id} not found.")
    return success_response(data=quote)


# --- Sales Order Endpoints ---

@router.post("/orders", dependencies=[Depends(require_permission("sales:orders:write"))])
async def create_order(
    data: SalesOrderCreate,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "orders")
    try:
        order = await order_service.create_order(session, data)
        return success_response(data=order)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/orders", dependencies=[Depends(require_permission("sales:orders:read"))])
async def list_orders(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "orders")
    total_stmt = select(func.count()).select_from(SalesOrder).where(SalesOrder.is_deleted == False)
    total = (await session.execute(total_stmt)).scalar() or 0

    items = await order_service.get_all_orders(session, skip=pagination.offset, limit=pagination.limit)
    return paginated_response(data=items, total=total, page=pagination.page, page_size=pagination.page_size)


@router.get("/orders/{id}", dependencies=[Depends(require_permission("sales:orders:read"))])
async def get_order(id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("sales", "orders")
    order = await order_service.get_order(session, id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Sales Order with ID {id} not found.")
    return success_response(data=order)


@router.post("/orders/{id}/confirm", dependencies=[Depends(require_permission("sales:orders:write"))])
async def confirm_order(id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("sales", "orders")
    try:
        order = await order_service.confirm_order(session, id)
        return success_response(data=order)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except StateTransitionError as e:
        raise HTTPException(status_code=422, detail=e.message)


@router.post("/orders/{id}/cancel", dependencies=[Depends(require_permission("sales:orders:write"))])
async def cancel_order(id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("sales", "orders")
    try:
        order = await order_service.cancel_order(session, id)
        return success_response(data=order)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except StateTransitionError as e:
        raise HTTPException(status_code=422, detail=e.message)


@router.post("/orders/{id}/clone", dependencies=[Depends(require_permission("sales:orders:write"))])
async def clone_order(id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("sales", "orders")
    try:
        order = await order_service.clone_order(session, id)
        return success_response(data=order)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
