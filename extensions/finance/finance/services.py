import logging
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from .models import FinanceRecord
from .schemas import FinanceRecordCreate

logger = logging.getLogger(__name__)


async def create_finance_record(session: AsyncSession, data: FinanceRecordCreate) -> FinanceRecord:
    db_obj = FinanceRecord.model_validate(data)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj
