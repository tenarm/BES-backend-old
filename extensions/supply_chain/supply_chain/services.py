import logging
from sqlalchemy.ext.asyncio import AsyncSession
from .models import SupplyChainEntity
from .schemas import SupplyChainEntityCreate

logger = logging.getLogger(__name__)

async def create_entity(session: AsyncSession, data: SupplyChainEntityCreate) -> SupplyChainEntity:
    db_obj = SupplyChainEntity.model_validate(data)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj
