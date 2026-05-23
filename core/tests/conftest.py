import os
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

# Set the database URL environment variable to in-memory sqlite before imports
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

# Set JWT secret key for JWT token generation in tests
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-testing-only-12345"

# Suppress echo logging in test outputs unless SQL_ECHO=true is explicitly set
if "SQL_ECHO" not in os.environ:
    os.environ["SQL_ECHO"] = "false"

from core.database import get_engine, get_async_session

@pytest.fixture(scope="session")
def test_engine():
    """Returns the cached in-memory SQLite engine."""
    return get_engine()

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database(test_engine):
    """Automatically registers all models and creates database tables for testing."""
    # Ensure all core models are imported so SQLModel registers them
    from core import models  # noqa: F401
    
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Yields a database session and rolls it back after test completion."""
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session

@pytest.fixture
def test_app(db_session) -> FastAPI:
    """Returns a test FastAPI application with dependency overrides."""
    from core.router import router as auth_router, notification_router, audit_router
    
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(notification_router)
    app.include_router(audit_router)
    
    # Override FastAPI DB session dependency to use the isolated test session
    async def override_get_async_session():
        yield db_session
        
    app.dependency_overrides[get_async_session] = override_get_async_session
    return app

@pytest_asyncio.fixture
async def client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """Yields an async HTTP client for executing requests against the test application."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://testserver") as ac:
        yield ac
