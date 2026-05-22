import logging
from sqlalchemy.ext.asyncio import AsyncSession
from .models import InventoryEntity
from .schemas import InventoryEntityCreate

logger = logging.getLogger(__name__)

async def create_entity(session: AsyncSession, data: InventoryEntityCreate) -> InventoryEntity:
    db_obj = InventoryEntity.model_validate(data)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj
