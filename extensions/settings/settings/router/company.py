import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from core.database import get_async_session
from core.responses import success_response, paginated_response
from core.pagination import PaginationParams
from core.licensing import require_licensed_feature
from core.rbac import require_permission
from core.exceptions import ConcurrencyError

from ..models import CompanyProfile, Subsidiary, FiscalCalendar, PostingPeriod, TaxProfile
from ..schemas import (
    CompanyProfileCreate, CompanyProfileUpdate,
    SubsidiaryCreate, SubsidiaryUpdate,
    FiscalCalendarCreate, FiscalCalendarUpdate,
    TaxProfileCreate, TaxProfileUpdate
)
from ..services import (
    CompanyProfileService, SubsidiaryService, FiscalCalendarService,
    PostingPeriodService, TaxProfileService
)

router = APIRouter()

# --- Company Profile Endpoints ---

@router.get("/company-profile", dependencies=[Depends(require_permission("settings:company:read"))])
async def get_company_profile(session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("settings", "company_setup")
    profile = await CompanyProfileService.get_profile(session)
    if not profile:
        raise HTTPException(status_code=404, detail="Company profile not configured yet.")
    return success_response(data=profile)

@router.post("/company-profile", dependencies=[Depends(require_permission("settings:company:write"))])
async def create_company_profile(data: CompanyProfileCreate, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("settings", "company_setup")
    try:
        profile = await CompanyProfileService.create_profile(session, data)
        return success_response(data=profile)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/company-profile/{id}", dependencies=[Depends(require_permission("settings:company:write"))])
async def update_company_profile(
    id: uuid.UUID,
    data: CompanyProfileUpdate,
    version_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("settings", "company_setup")
    try:
        profile = await CompanyProfileService.update_profile(session, id, data, version_id)
        return success_response(data=profile)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConcurrencyError as e:
        raise HTTPException(status_code=409, detail=str(e))

# --- Subsidiary Endpoints ---

@router.post("/subsidiaries", dependencies=[Depends(require_permission("settings:subsidiary:write"))])
async def create_subsidiary(data: SubsidiaryCreate, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("settings", "company_setup")
    try:
        item = await SubsidiaryService.create_subsidiary(session, data)
        return success_response(data=item)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/subsidiaries", dependencies=[Depends(require_permission("settings:subsidiary:read"))])
async def list_subsidiaries(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("settings", "company_setup")
    
    count_stmt = select(func.count()).select_from(Subsidiary).where(Subsidiary.is_deleted == False)
    total = (await session.execute(count_stmt)).scalar() or 0
    
    stmt = (
        select(Subsidiary)
        .where(Subsidiary.is_deleted == False)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    result = await session.execute(stmt)
    items = result.scalars().all()
    
    return paginated_response(data=items, total=total, page=pagination.page, page_size=pagination.page_size)

@router.get("/subsidiaries/{id}", dependencies=[Depends(require_permission("settings:subsidiary:read"))])
async def get_subsidiary(id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("settings", "company_setup")
    stmt = select(Subsidiary).where(Subsidiary.id == id).where(Subsidiary.is_deleted == False)
    res = await session.execute(stmt)
    item = res.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail=f"Subsidiary with ID {id} not found.")
    return success_response(data=item)

@router.put("/subsidiaries/{id}", dependencies=[Depends(require_permission("settings:subsidiary:write"))])
async def update_subsidiary(
    id: uuid.UUID,
    data: SubsidiaryUpdate,
    version_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("settings", "company_setup")
    try:
        item = await SubsidiaryService.update_subsidiary(session, id, data, version_id)
        return success_response(data=item)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConcurrencyError as e:
        raise HTTPException(status_code=409, detail=str(e))

# --- Fiscal Calendar Endpoints ---

@router.post("/fiscal-calendars", dependencies=[Depends(require_permission("settings:fiscal_calendar:write"))])
async def create_fiscal_calendar(data: FiscalCalendarCreate, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("settings", "company_setup")
    try:
        cal = await FiscalCalendarService.create_fiscal_year(session, data)
        return success_response(data=cal)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/fiscal-calendars", dependencies=[Depends(require_permission("settings:fiscal_calendar:read"))])
async def list_fiscal_calendars(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("settings", "company_setup")
    count_stmt = select(func.count()).select_from(FiscalCalendar).where(FiscalCalendar.is_deleted == False)
    total = (await session.execute(count_stmt)).scalar() or 0
    
    stmt = (
        select(FiscalCalendar)
        .where(FiscalCalendar.is_deleted == False)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    result = await session.execute(stmt)
    items = result.scalars().all()
    return paginated_response(data=items, total=total, page=pagination.page, page_size=pagination.page_size)

@router.put("/fiscal-calendars/{id}", dependencies=[Depends(require_permission("settings:fiscal_calendar:write"))])
async def update_fiscal_calendar(
    id: uuid.UUID,
    data: FiscalCalendarUpdate,
    version_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("settings", "company_setup")
    try:
        cal = await FiscalCalendarService.update_fiscal_year(session, id, data, version_id)
        return success_response(data=cal)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConcurrencyError as e:
        raise HTTPException(status_code=409, detail=str(e))

# --- Posting Period Endpoints ---

@router.patch("/posting-periods/{id}/lock", dependencies=[Depends(require_permission("settings:fiscal_calendar:write"))])
async def lock_posting_period(
    id: uuid.UUID,
    is_locked: bool,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("settings", "company_setup")
    try:
        period = await PostingPeriodService.update_period_status(session, id, is_locked)
        return success_response(data=period)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- Tax Profile Endpoints ---

@router.post("/tax-profiles", dependencies=[Depends(require_permission("settings:tax_profile:write"))])
async def create_tax_profile(data: TaxProfileCreate, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("settings", "company_setup")
    try:
        prof = await TaxProfileService.create_tax_profile(session, data)
        return success_response(data=prof)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/tax-profiles", dependencies=[Depends(require_permission("settings:tax_profile:read"))])
async def list_tax_profiles(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("settings", "company_setup")
    count_stmt = select(func.count()).select_from(TaxProfile).where(TaxProfile.is_deleted == False)
    total = (await session.execute(count_stmt)).scalar() or 0
    
    stmt = (
        select(TaxProfile)
        .where(TaxProfile.is_deleted == False)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    result = await session.execute(stmt)
    items = result.scalars().all()
    return paginated_response(data=items, total=total, page=pagination.page, page_size=pagination.page_size)

@router.put("/tax-profiles/{id}", dependencies=[Depends(require_permission("settings:tax_profile:write"))])
async def update_tax_profile(
    id: uuid.UUID,
    data: TaxProfileUpdate,
    version_id: int,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("settings", "company_setup")
    try:
        prof = await TaxProfileService.update_tax_profile(session, id, data, version_id)
        return success_response(data=prof)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConcurrencyError as e:
        raise HTTPException(status_code=409, detail=str(e))
