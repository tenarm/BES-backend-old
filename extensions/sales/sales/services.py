import logging
from sqlalchemy.ext.asyncio import AsyncSession
from .models import SalesEntity
from .schemas import SalesEntityCreate

logger = logging.getLogger(__name__)

async def create_entity(session: AsyncSession, data: SalesEntityCreate) -> SalesEntity:
    db_obj = SalesEntity.model_validate(data)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj
