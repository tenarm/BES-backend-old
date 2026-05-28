import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from core.database import get_async_session
from core.responses import success_response, paginated_response
from core.pagination import PaginationParams
from core.licensing import require_licensed_feature
from core.rbac import require_permission
from core.exceptions import ValidationError, EntityNotFoundError, StateTransitionError

from .schemas import InventoryShipmentCreate
from .services import ShipmentService
from .models import InventoryShipment

router = APIRouter(prefix="/api/v1/inventory", tags=["Inventory"])
shipment_service = ShipmentService()


@router.post("/shipments", dependencies=[Depends(require_permission("inventory:shipments:write"))])
async def create_shipment(
    data: InventoryShipmentCreate,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("inventory", "stock_reservations")
    try:
        shipment = await shipment_service.create_shipment(session, data)
        return success_response(data=shipment)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/shipments", dependencies=[Depends(require_permission("inventory:shipments:read"))])
async def list_shipments(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("inventory", "stock_reservations")
    total_stmt = select(func.count()).select_from(InventoryShipment).where(InventoryShipment.is_deleted == False)
    total = (await session.execute(total_stmt)).scalar() or 0

    items = await shipment_service.get_all_shipments(session, skip=pagination.offset, limit=pagination.limit)
    return paginated_response(data=items, total=total, page=pagination.page, page_size=pagination.page_size)


@router.get("/shipments/{id}", dependencies=[Depends(require_permission("inventory:shipments:read"))])
async def get_shipment(id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("inventory", "stock_reservations")
    shipment = await shipment_service.get_shipment(session, id)
    if not shipment:
        raise HTTPException(status_code=404, detail=f"Shipment with ID {id} not found.")
    return success_response(data=shipment)


@router.post("/shipments/{id}/dispatch", dependencies=[Depends(require_permission("inventory:shipments:write"))])
async def dispatch_shipment(id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("inventory", "stock_reservations")
    try:
        shipment = await shipment_service.dispatch_shipment(session, id)
        return success_response(data=shipment)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except StateTransitionError as e:
        raise HTTPException(status_code=422, detail=e.message)
