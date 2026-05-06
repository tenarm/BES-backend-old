from contextvars import ContextVar
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from typing import AsyncGenerator
import os

# Context variable for multi-tenancy
subsidiary_id_context: ContextVar[str | None] = ContextVar("subsidiary_id_context", default=None)

# Database URL. Defaults to async SQLite for local testing, can be overridden by asyncpg for prod
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./erp.db")

engine = create_async_engine(DATABASE_URL, echo=True)

async_session_maker = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
