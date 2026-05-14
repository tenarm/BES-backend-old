import os
from contextvars import ContextVar
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker
from typing import AsyncGenerator

# Context variable for multi-tenancy
subsidiary_id_context: ContextVar[str | None] = ContextVar("subsidiary_id_context", default=None)

# --- Engine Factory (supports multi-tenant DB-per-client) ---
_engines: dict[str, AsyncEngine] = {}

def get_engine(database_url: str | None = None) -> AsyncEngine:
    """
    Factory function for async engines.
    Caches engines by URL to avoid creating duplicates.
    SQL echo is controlled via the SQL_ECHO environment variable.
    """
    url = database_url or os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./bes.db")
    if url not in _engines:
        echo = os.getenv("SQL_ECHO", "false").lower() == "true"
        _engines[url] = create_async_engine(url, echo=echo)
    return _engines[url]

# Backward-compatible default engine (set after DATABASE_URL is configured)
def _get_default_engine() -> AsyncEngine:
    return get_engine()

def get_session_maker(eng: AsyncEngine | None = None) -> sessionmaker:
    """Creates an async session maker bound to the given (or default) engine."""
    target_engine = eng or _get_default_engine()
    return sessionmaker(
        target_engine, class_=AsyncSession, expire_on_commit=False
    )

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session."""
    session_maker = get_session_maker()
    async with session_maker() as session:
        yield session
