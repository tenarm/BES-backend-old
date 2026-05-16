from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from .models import FinanceRecord
from .schemas import FinanceRecordCreate
from .services import create_finance_record
from core.database import get_async_session
from core.responses import success_response, paginated_response
from core.pagination import PaginationParams

router = APIRouter(prefix="/api/v1/finance", tags=["finance"])


@router.get("/records")
async def list_finance_records(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    count_stmt = select(func.count()).select_from(FinanceRecord).where(FinanceRecord.is_deleted == False)
    total = (await session.execute(count_stmt)).scalar() or 0
    
    stmt = (
        select(FinanceRecord)
        .where(FinanceRecord.is_deleted == False)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    result = await session.execute(stmt)
    items = result.scalars().all()
    
    return paginated_response(data=items, total=total, page=pagination.page, page_size=pagination.page_size)


@router.post("/records")
async def create_finance_record_endpoint(
    data: FinanceRecordCreate,
    session: AsyncSession = Depends(get_async_session)
):
    item = await create_finance_record(session, data)
    return success_response(data=item)
