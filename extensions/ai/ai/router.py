from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from .models import AiEntity
from .schemas import AiEntityCreate
from .services import create_entity
from core.database import get_async_session
from core.responses import success_response, paginated_response
from core.pagination import PaginationParams
from core.licensing import require_licensed_feature
from core.rbac import require_permission

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])

@router.get("/entities", dependencies=[Depends(require_permission("ai:entity:read"))])
async def list_entities(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("ai", "entity_management")

    count_stmt = select(func.count()).select_from(AiEntity).where(AiEntity.is_deleted == False)
    total = (await session.execute(count_stmt)).scalar() or 0
    
    stmt = (
        select(AiEntity)
        .where(AiEntity.is_deleted == False)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    result = await session.execute(stmt)
    items = result.scalars().all()
    
    return paginated_response(data=items, total=total, page=pagination.page, page_size=pagination.page_size)

@router.post("/entities", dependencies=[Depends(require_permission("ai:entity:write"))])
async def create_entity_endpoint(
    data: AiEntityCreate,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("ai", "entity_management")

    item = await create_entity(session, data)
    return success_response(data=item)
