import uuid
from typing import Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from .models import SupplyChainEntity
from .schemas import (
    SupplyChainEntityCreate, SupplierOnboard, SupplierUpdate, SupplierCertificationCreate
)
from .services import (
    create_entity, SupplierService, DuplicateTaxRegistrationError,
    InvalidLeadTimeDaysError, InvalidTargetScoreError, SupplierNotFoundError
)
from core.database import get_async_session
from core.responses import success_response, paginated_response
from core.pagination import PaginationParams
from core.licensing import require_licensed_feature
from core.rbac import require_permission
from core.exceptions import ConcurrencyError

router = APIRouter(prefix="/api/v1/supply-chain", tags=["supply_chain"])

# --- Boilerplate Entity Handlers for Backward Compatibility ---
@router.get("/entities", dependencies=[Depends(require_permission("supply_chain:entity:read"))])
async def list_entities(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("supply_chain", "entity_management")

    count_stmt = select(func.count()).select_from(SupplyChainEntity).where(SupplyChainEntity.is_deleted == False)
    total = (await session.execute(count_stmt)).scalar() or 0
    
    stmt = (
        select(SupplyChainEntity)
        .where(SupplyChainEntity.is_deleted == False)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    result = await session.execute(stmt)
    items = result.scalars().all()
    
    return paginated_response(data=items, total=total, page=pagination.page, page_size=pagination.page_size)

@router.post("/entities", dependencies=[Depends(require_permission("supply_chain:entity:write"))])
async def create_entity_endpoint(
    data: SupplyChainEntityCreate,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("supply_chain", "entity_management")

    item = await create_entity(session, data)
    return success_response(data=item)


# --- Core Supplier Master Handlers per Proposed Plan ---
@router.get("/suppliers", dependencies=[Depends(require_permission("supply-chain:supplier_master:read"))])
async def list_suppliers_endpoint(
    search: Optional[str] = None,
    status: Optional[str] = None,
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("supply_chain", "supplier_master")
    items, total = await SupplierService.list_suppliers(
        session, search=search, status=status, page=pagination.page, page_size=pagination.page_size
    )
    return paginated_response(data=items, total=total, page=pagination.page, page_size=pagination.page_size)

@router.get("/suppliers/{id}", dependencies=[Depends(require_permission("supply-chain:supplier_master:read"))])
async def get_supplier_endpoint(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("supply_chain", "supplier_master")
    item = await SupplierService.get_supplier(session, vendor_id=id)
    if not item:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    return success_response(data=item)

@router.post("/suppliers", dependencies=[Depends(require_permission("supply-chain:supplier_master:write"))])
async def onboard_supplier_endpoint(
    data: SupplierOnboard,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("supply_chain", "supplier_master")
    try:
        item = await SupplierService.onboard_supplier(session, data=data)
        return success_response(data=item)
    except (DuplicateTaxRegistrationError, InvalidLeadTimeDaysError, InvalidTargetScoreError) as e:
        raise HTTPException(status_code=422, detail=str(e))

@router.put("/suppliers/{id}", dependencies=[Depends(require_permission("supply-chain:supplier_master:write"))])
async def update_supplier_endpoint(
    id: uuid.UUID,
    data: SupplierUpdate,
    version_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("supply_chain", "supplier_master")
    try:
        item = await SupplierService.update_supplier(
            session, vendor_id=id, data=data, version_id=version_id
        )
        return success_response(data=item)
    except ConcurrencyError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except (SupplierNotFoundError, InvalidLeadTimeDaysError, InvalidTargetScoreError) as e:
        raise HTTPException(status_code=422, detail=str(e))

@router.patch("/suppliers/{id}/holds", dependencies=[Depends(require_permission("supply-chain:compliance_control:write"))])
async def toggle_supplier_holds_endpoint(
    id: uuid.UUID,
    purchasing_hold: Optional[bool] = None,
    payment_hold: Optional[bool] = None,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("supply_chain", "supplier_master")
    try:
        item = await SupplierService.toggle_supplier_holds(
            session, vendor_id=id, purchasing_hold=purchasing_hold, payment_hold=payment_hold
        )
        return success_response(data=item)
    except SupplierNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/suppliers/{id}/certifications", dependencies=[Depends(require_permission("supply-chain:compliance_control:write"))])
async def add_certification_endpoint(
    id: uuid.UUID,
    data: SupplierCertificationCreate,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("supply_chain", "supplier_premium")
    try:
        item = await SupplierService.add_certification(session, vendor_id=id, data=data)
        return success_response(data=item)
    except SupplierNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/suppliers/{id}/evaluate-performance", dependencies=[Depends(require_permission("supply-chain:supplier_master:read"))])
async def evaluate_performance_endpoint(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("supply_chain", "supplier_premium")
    try:
        item = await SupplierService.evaluate_performance_metrics(session, vendor_id=id)
        return success_response(data=item)
    except SupplierNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
