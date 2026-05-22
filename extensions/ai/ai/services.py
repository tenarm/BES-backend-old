import logging
from sqlalchemy.ext.asyncio import AsyncSession
from .models import AiEntity
from .schemas import AiEntityCreate

logger = logging.getLogger(__name__)

async def create_entity(session: AsyncSession, data: AiEntityCreate) -> AiEntity:
    db_obj = AiEntity.model_validate(data)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj
