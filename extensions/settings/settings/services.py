import logging
from sqlalchemy.ext.asyncio import AsyncSession
from .models import SettingsEntity
from .schemas import SettingsEntityCreate

logger = logging.getLogger(__name__)

async def create_entity(session: AsyncSession, data: SettingsEntityCreate) -> SettingsEntity:
    db_obj = SettingsEntity.model_validate(data)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj
