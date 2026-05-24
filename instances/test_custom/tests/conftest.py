import sys
from pathlib import Path

# Add core workspace directory to path to resolve core tests conftest
core_path = str(Path(__file__).resolve().parents[3] / "core")
if core_path not in sys.path:
    sys.path.append(core_path)

from tests.conftest import *  # Inherit and reuse all core fixtures
from fastapi import FastAPI
from core.database import get_async_session

import pytest
import pytest_asyncio
from sqlmodel import SQLModel

@pytest.fixture
def test_app(db_session) -> FastAPI:
    """FastAPI app override for instance integration testing, importing the client's actual main FastAPI app."""
    from test_custom.main import app as main_app
    
    # Overwrite the db dependency in the actual fused client app
    async def override_get_async_session():
        yield db_session
    main_app.dependency_overrides[get_async_session] = override_get_async_session
    
    return main_app

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database(test_engine):
    """Automatically registers all models and creates database tables for testing."""
    # Ensure all core models are imported so SQLModel registers them
    from core import models  # noqa: F401
    
    # Force settings models to register on SQLModel metadata
    from settings.models import (  # noqa: F401
        CompanyProfile,
        Subsidiary,
        FiscalYear,
        PostingPeriod,
        TaxProfile,
        SharingRule,
        IntercompanyAccount,
    )
    
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
