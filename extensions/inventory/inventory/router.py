import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from .models import InventoryEntity, InventoryWarehouseLocation
from core.models import UOM
from .schemas import (
    InventoryEntityCreate,
    ItemDetailsCreate,
    ItemDetailsUpdate,
    ItemDetailsRead,
    UomConversionCreate,
    UomConversionRead,
    LotCreate,
    LotRead,
    LocationCreate,
    LocationUpdate,
    LocationRead
)
from .services import (
    create_entity,
    ItemMasterService,
    InventoryLotService,
    WarehouseLocationService,
    ItemDomainException,
    DuplicateSkuError,
    InvalidSkuFormatError,
    CostingMethodLockedError,
    CircularUomConversionError,
    NegativeNumericValueError,
    ConcurrencyError,
    InvalidCodeFormatError,
    CircularHierarchyError,
    ActiveStockLocationError,
    NegativeCapacityError
)
from core.database import get_async_session
from core.responses import success_response, paginated_response
from core.pagination import PaginationParams
from core.licensing import require_licensed_feature
from core.rbac import require_permission

router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])

# --- UOM Retrieval Endpoints ---

@router.get("/uoms", dependencies=[Depends(require_permission("inventory:item_master:read"))])
async def list_uoms(
    session: AsyncSession = Depends(get_async_session)
):
    """Lists all available units of measure."""
    require_licensed_feature("inventory", "item_master")
    stmt = select(UOM).where(UOM.is_deleted == False)
    result = await session.execute(stmt)
    uoms = result.scalars().all()
    return success_response(data=uoms)


# --- Legacy/Boilerplate Endpoints (Preserving compatibility) ---

@router.get("/entities", dependencies=[Depends(require_permission("inventory:entity:read"))])
async def list_entities(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("inventory", "entity_management")

    count_stmt = select(func.count()).select_from(InventoryEntity).where(InventoryEntity.is_deleted == False)
    total = (await session.execute(count_stmt)).scalar() or 0
    
    stmt = (
        select(InventoryEntity)
        .where(InventoryEntity.is_deleted == False)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    result = await session.execute(stmt)
    items = result.scalars().all()
    
    return paginated_response(data=items, total=total, page=pagination.page, page_size=pagination.page_size)


@router.post("/entities", dependencies=[Depends(require_permission("inventory:entity:write"))])
async def create_entity_endpoint(
    data: InventoryEntityCreate,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("inventory", "entity_management")

    item = await create_entity(session, data)
    return success_response(data=item)


# --- Item Master Endpoints ---

@router.get("/items", dependencies=[Depends(require_permission("inventory:item_master:read"))])
async def list_items(
    search: Optional[str] = Query(None, description="Search by name or SKU"),
    subsidiary_id: Optional[str] = Query(None, description="Scope by subsidiary"),
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    """Retrieves a paginated list of catalog items."""
    require_licensed_feature("inventory", "item_master")

    items, total = await ItemMasterService.list_items(
        session=session,
        search=search,
        subsidiary_id=subsidiary_id,
        offset=pagination.offset,
        limit=pagination.limit
    )
    return paginated_response(data=items, total=total, page=pagination.page, page_size=pagination.page_size)


@router.get("/items/{id}", dependencies=[Depends(require_permission("inventory:item_master:read"))])
async def get_item_details(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session)
):
    """Retrieves standard details and specifications for a single item."""
    require_licensed_feature("inventory", "item_master")

    item = await ItemMasterService.get_item(session, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return success_response(data=item)


@router.post("/items", dependencies=[Depends(require_permission("inventory:item_master:write"))])
async def onboard_item(
    data: ItemDetailsCreate,
    session: AsyncSession = Depends(get_async_session)
):
    """Registers a new item in the catalog."""
    require_licensed_feature("inventory", "item_master")

    try:
        item = await ItemMasterService.onboard_item(session, data)
        return success_response(data=item)
    except DuplicateSkuError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except InvalidSkuFormatError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except NegativeNumericValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ItemDomainException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/items/{id}", dependencies=[Depends(require_permission("inventory:item_master:write"))])
async def update_item_details(
    id: uuid.UUID,
    data: ItemDetailsUpdate,
    version_id: int = Query(..., description="Optimistic locking version checks"),
    session: AsyncSession = Depends(get_async_session)
):
    """Updates catalog variables for an item."""
    require_licensed_feature("inventory", "item_master")

    try:
        item = await ItemMasterService.update_item(session, id, data, version_id)
        return success_response(data=item)
    except ConcurrencyError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except CostingMethodLockedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NegativeNumericValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ItemDomainException as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- UOM Conversion Endpoints ---

@router.post("/items/{id}/uom-conversions", dependencies=[Depends(require_permission("inventory:item_master:write"))])
async def add_uom_conversion(
    id: uuid.UUID,
    data: UomConversionCreate,
    session: AsyncSession = Depends(get_async_session)
):
    """Registers a UOM conversion multiplier for an item."""
    require_licensed_feature("inventory", "uom_conversions")

    try:
        conversion = await ItemMasterService.add_uom_conversion(session, id, data)
        return success_response(data=conversion)
    except CircularUomConversionError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except NegativeNumericValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ItemDomainException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/items/{id}/uom-conversions", dependencies=[Depends(require_permission("inventory:item_master:read"))])
async def list_uom_conversions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session)
):
    """Lists UOM conversion rules for an item."""
    require_licensed_feature("inventory", "uom_conversions")

    conversions = await ItemMasterService.list_conversions(session, id)
    return success_response(data=conversions)


# --- Lot Master Endpoints ---

@router.post("/items/{id}/lots", dependencies=[Depends(require_permission("inventory:item_master:write"))])
async def create_lot(
    id: uuid.UUID,
    data: LotCreate,
    session: AsyncSession = Depends(get_async_session)
):
    """Registers a new traceable lot/batch for an item."""
    # Premium feature tier gating
    require_licensed_feature("inventory", "lot_tracking")

    try:
        lot = await InventoryLotService.create_lot(session, id, data)
        return success_response(data=lot)
    except ItemDomainException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/items/{id}/lots", dependencies=[Depends(require_permission("inventory:item_master:read"))])
async def list_lots(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session)
):
    """Lists active lots/batches for an item."""
    require_licensed_feature("inventory", "lot_tracking")

    lots = await InventoryLotService.list_lots(session, id)
    return success_response(data=lots)


# --- Warehouse Location Endpoints ---

@router.get("/locations", dependencies=[Depends(require_permission("inventory:warehouse_location:read"))])
async def list_locations(
    parent_id: Optional[uuid.UUID] = Query(None, description="Filter by parent location"),
    search: Optional[str] = Query(None, description="Search by name or code"),
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    """Retrieves a paginated list of warehouse locations."""
    require_licensed_feature("inventory", "warehouse_location")

    count_stmt = select(func.count()).select_from(InventoryWarehouseLocation).where(
        InventoryWarehouseLocation.is_deleted == False
    )
    if parent_id is not None:
        count_stmt = count_stmt.where(InventoryWarehouseLocation.parent_id == parent_id)
    if search:
        count_stmt = count_stmt.where(
            InventoryWarehouseLocation.name.ilike(f"%{search}%") | 
            InventoryWarehouseLocation.code.ilike(f"%{search}%")
        )
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = select(InventoryWarehouseLocation).where(
        InventoryWarehouseLocation.is_deleted == False
    ).order_by(InventoryWarehouseLocation.code.asc())
    if parent_id is not None:
        stmt = stmt.where(InventoryWarehouseLocation.parent_id == parent_id)
    if search:
        stmt = stmt.where(
            InventoryWarehouseLocation.name.ilike(f"%{search}%") | 
            InventoryWarehouseLocation.code.ilike(f"%{search}%")
        )
    
    stmt = stmt.offset(pagination.offset).limit(pagination.limit)
    res = await session.execute(stmt)
    locations = res.scalars().all()

    return paginated_response(
        data=locations, 
        total=total, 
        page=pagination.page, 
        page_size=pagination.page_size
    )


@router.get("/locations/{id}", dependencies=[Depends(require_permission("inventory:warehouse_location:read"))])
async def get_location_details(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session)
):
    """Retrieves details of a single warehouse location."""
    require_licensed_feature("inventory", "warehouse_location")
    
    stmt = select(InventoryWarehouseLocation).where(
        InventoryWarehouseLocation.id == id,
        InventoryWarehouseLocation.is_deleted == False
    )
    location = (await session.execute(stmt)).scalars().first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
        
    return success_response(data=location)


@router.post("/locations", dependencies=[Depends(require_permission("inventory:warehouse_location:write"))])
async def create_location(
    data: LocationCreate,
    session: AsyncSession = Depends(get_async_session)
):
    """Onboards a new physical warehouse or storage zone."""
    require_licensed_feature("inventory", "warehouse_location")

    try:
        location = await WarehouseLocationService.create_location(session, data)
        return success_response(data=location)
    except InvalidCodeFormatError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except NegativeCapacityError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ItemDomainException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/locations/{id}", dependencies=[Depends(require_permission("inventory:warehouse_location:write"))])
async def update_location(
    id: uuid.UUID,
    data: LocationUpdate,
    version_id: int = Query(..., description="Optimistic locking checks"),
    session: AsyncSession = Depends(get_async_session)
):
    """Modifies warehouse location parameters."""
    require_licensed_feature("inventory", "warehouse_location")

    try:
        location = await WarehouseLocationService.update_location(session, id, data, version_id)
        return success_response(data=location)
    except ConcurrencyError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except CircularHierarchyError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except NegativeCapacityError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ActiveStockLocationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ItemDomainException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/locations/{id}/audit-lock", dependencies=[Depends(require_permission("inventory:warehouse_location:write"))])
async def toggle_audit_lock(
    id: uuid.UUID,
    locked: bool = Query(..., description="True to lock location for audits"),
    session: AsyncSession = Depends(get_async_session)
):
    """Locks or unlocks a location from inventory movements."""
    require_licensed_feature("inventory", "warehouse_location")

    stmt = select(InventoryWarehouseLocation).where(
        InventoryWarehouseLocation.id == id,
        InventoryWarehouseLocation.is_deleted == False
    )
    location = (await session.execute(stmt)).scalars().first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    location.audit_locked = locked
    session.add(location)
    await session.commit()
    await session.refresh(location)

    return success_response(data={"id": str(location.id), "audit_locked": location.audit_locked})
