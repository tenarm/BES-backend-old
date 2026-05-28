from typing import TypeVar, Type, Optional, Sequence, Generic, Any
from sqlmodel import select, SQLModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError
from .database import subsidiary_id_context
from .middleware import correlation_id_context, current_user_id_context, current_user_name_context
from .exceptions import ConcurrencyError
import uuid

ModelType = TypeVar("ModelType", bound=SQLModel)

class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    def _apply_scopes(self, stmt):
        """
        Automatically injects row-level security and soft-deletion scopes.
        """
        # Apply subsidiary isolation
        if hasattr(self.model, "subsidiary_id"):
            subs_id = subsidiary_id_context.get()
            if subs_id:
                stmt = stmt.where(self.model.subsidiary_id == subs_id)
        
        # Apply soft delete filter
        if hasattr(self.model, "is_deleted"):
            stmt = stmt.where(self.model.is_deleted == False)
            
        return stmt

    async def get(self, session: AsyncSession, id: uuid.UUID | str) -> Optional[ModelType]:
        stmt = select(self.model).where(self.model.id == id)
        stmt = self._apply_scopes(stmt)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def get_with_lock(
        self,
        session: AsyncSession,
        id: uuid.UUID | str,
        nowait: bool = False,
        skip_locked: bool = False
    ) -> Optional[ModelType]:
        """
        Fetches a record by ID and applies a pessimistic lock (FOR UPDATE).
        """
        stmt = select(self.model).where(self.model.id == id)
        stmt = self._apply_scopes(stmt)
        stmt = stmt.with_for_update(nowait=nowait, skip_locked=skip_locked)
        result = await session.execute(stmt)
        return result.scalars().first()


    async def get_all(self, session: AsyncSession, skip: int = 0, limit: int = 100) -> Sequence[ModelType]:
        stmt = select(self.model).offset(skip).limit(limit)
        stmt = self._apply_scopes(stmt)
        result = await session.execute(stmt)
        return result.scalars().all()

    async def create(self, session: AsyncSession, obj_in: ModelType) -> ModelType:
        # Auto-inject subsidiary_id on creation if missing
        if hasattr(obj_in, "subsidiary_id") and getattr(obj_in, "subsidiary_id", None) is None:
            subs_id = subsidiary_id_context.get()
            if subs_id:
                obj_in.subsidiary_id = subs_id

        # Auto-inject created_by from current user context
        if hasattr(obj_in, "created_by") and getattr(obj_in, "created_by", None) is None:
            user_name = current_user_name_context.get()
            if user_name:
                obj_in.created_by = user_name
        
        session.add(obj_in)
        await session.flush()
        await session.refresh(obj_in)
        return obj_in

    async def update(self, session: AsyncSession, db_obj: ModelType, obj_in: dict[str, Any] | SQLModel) -> ModelType:
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        
        # Concurrency verification: check version_id if present
        if hasattr(db_obj, "version_id") and "version_id" in update_data:
            client_version = update_data["version_id"]
            if client_version is not None and db_obj.version_id != client_version:
                raise ConcurrencyError(
                    f"Stale data detected. Database version is {db_obj.version_id}, "
                    f"but update request specified version {client_version}."
                )

        for field, value in update_data.items():
            setattr(db_obj, field, value)
            
        session.add(db_obj)
        await session.flush()
        await session.refresh(db_obj)
        return db_obj


    async def delete(self, session: AsyncSession, db_obj: ModelType) -> ModelType:
        """
        Soft deletes the object if 'is_deleted' exists, otherwise hard deletes.
        """
        if hasattr(db_obj, "is_deleted"):
            db_obj.is_deleted = True
            session.add(db_obj)
            await session.flush()
            await session.refresh(db_obj)
        else:
            await session.delete(db_obj)
            await session.flush()
        return db_obj

    async def count(self, session: AsyncSession) -> int:
        """Returns total count of records matching current scopes."""
        from sqlalchemy import func
        stmt = select(func.count()).select_from(self.model)
        stmt = self._apply_scopes(stmt)
        result = await session.execute(stmt)
        return result.scalar_one()

    async def filter_by(self, session: AsyncSession, skip: int = 0, limit: int = 100, **kwargs) -> Sequence[ModelType]:
        """Filters records by keyword arguments matching model columns."""
        stmt = select(self.model).offset(skip).limit(limit)
        for key, value in kwargs.items():
            if hasattr(self.model, key):
                stmt = stmt.where(getattr(self.model, key) == value)
        stmt = self._apply_scopes(stmt)
        result = await session.execute(stmt)
        return result.scalars().all()
