import logging
from sqlalchemy.ext.asyncio import AsyncSession
from .models import FinanceEntity
from .schemas import FinanceEntityCreate

logger = logging.getLogger(__name__)

async def create_entity(session: AsyncSession, data: FinanceEntityCreate) -> FinanceEntity:
    db_obj = FinanceEntity.model_validate(data)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj
