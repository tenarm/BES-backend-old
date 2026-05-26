import uuid
from typing import Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from .models import SalesEntity
from .schemas import (
    SalesEntityCreate, CustomerCommercialOnboard, CustomerCommercialUpdate
)
from .services import (
    create_entity, CustomerSalesService, DuplicateTaxRegistrationError,
    InvalidCreditLimitError, UnsupportedCurrencyError, CustomerNotFoundError
)
from core.database import get_async_session
from core.responses import success_response, paginated_response
from core.pagination import PaginationParams
from core.licensing import require_licensed_feature
from core.rbac import require_permission
from core.exceptions import ConcurrencyError

router = APIRouter(prefix="/api/v1/sales", tags=["sales"])

@router.get("/entities", dependencies=[Depends(require_permission("sales:entity:read"))])
async def list_entities(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "entity_management")

    count_stmt = select(func.count()).select_from(SalesEntity).where(SalesEntity.is_deleted == False)
    total = (await session.execute(count_stmt)).scalar() or 0
    
    stmt = (
        select(SalesEntity)
        .where(SalesEntity.is_deleted == False)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    result = await session.execute(stmt)
    items = result.scalars().all()
    
    return paginated_response(data=items, total=total, page=pagination.page, page_size=pagination.page_size)

@router.post("/entities", dependencies=[Depends(require_permission("sales:entity:write"))])
async def create_entity_endpoint(
    data: SalesEntityCreate,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "entity_management")

    item = await create_entity(session, data)
    return success_response(data=item)

@router.get("/customers", dependencies=[Depends(require_permission("sales:customer_master:read"))])
async def list_customers_endpoint(
    search: Optional[str] = None,
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "customer_master")
    items, total = await CustomerSalesService.list_customers(
        session, search=search, page=pagination.page, page_size=pagination.page_size
    )
    return paginated_response(data=items, total=total, page=pagination.page, page_size=pagination.page_size)

@router.get("/customers/{id}", dependencies=[Depends(require_permission("sales:customer_master:read"))])
async def get_customer_endpoint(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "customer_master")
    item = await CustomerSalesService.get_customer(session, customer_id=id)
    if not item:
        raise HTTPException(status_code=404, detail="Customer not found.")
    return success_response(data=item)

@router.post("/customers", dependencies=[Depends(require_permission("sales:customer_master:write"))])
async def onboard_customer_endpoint(
    data: CustomerCommercialOnboard,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "customer_master")
    try:
        item = await CustomerSalesService.onboard_customer(session, data=data)
        return success_response(data=item)
    except (DuplicateTaxRegistrationError, InvalidCreditLimitError, UnsupportedCurrencyError) as e:
        raise HTTPException(status_code=422, detail=str(e))

@router.put("/customers/{id}", dependencies=[Depends(require_permission("sales:customer_master:write"))])
async def update_customer_endpoint(
    id: uuid.UUID,
    data: CustomerCommercialUpdate,
    version_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "customer_master")
    try:
        item = await CustomerSalesService.update_customer(
            session, customer_id=id, data=data, version_id=version_id
        )
        return success_response(data=item)
    except ConcurrencyError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except (CustomerNotFoundError, InvalidCreditLimitError, UnsupportedCurrencyError) as e:
        raise HTTPException(status_code=422, detail=str(e))

@router.patch("/customers/{id}/credit-hold", dependencies=[Depends(require_permission("sales:credit_control:write"))])
async def toggle_credit_hold_endpoint(
    id: uuid.UUID,
    credit_hold: bool,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "customer_master")
    try:
        item = await CustomerSalesService.toggle_credit_hold(session, customer_id=id, credit_hold=credit_hold)
        return success_response(data=item)
    except CustomerNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/customers/{id}/credit-check", dependencies=[Depends(require_permission("sales:customer_master:read"))])
async def check_credit_endpoint(
    id: uuid.UUID,
    order_amount: Decimal,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "customer_master")
    eligible = await CustomerSalesService.check_credit_eligibility(session, customer_id=id, order_amount=order_amount)
    return success_response(data={"eligible": eligible})

