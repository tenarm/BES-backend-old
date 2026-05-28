import sys
from pathlib import Path
import pytest

core_path = str(Path(__file__).resolve().parents[3] / "core")
if core_path not in sys.path:
    sys.path.append(core_path)

from tests.conftest import *  # Inherit and reuse all core fixtures
from fastapi import FastAPI
from core.database import get_async_session

from sales.manifest import manifest as sales_manifest


@pytest.fixture
def test_app(db_session) -> FastAPI:
    """FastAPI app override for sales extension tests."""
    from core.router import router as auth_router

    app = FastAPI()
    app.include_router(auth_router)

    app.include_router(sales_manifest.get_router())

    async def override_get_async_session():
        yield db_session
    app.dependency_overrides[get_async_session] = override_get_async_session

    return app


@pytest_asyncio.fixture(autouse=True)
async def seed_test_sequences(db_session):
    from core.sequences import SequenceService
    sequence_service = SequenceService()
    await sequence_service.ensure_sequence(db_session, "sales_quotation", "QT", pattern="{PREFIX}-{YYYY}{SEQ:05d}")
    await sequence_service.ensure_sequence(db_session, "sales_order", "SO", pattern="{PREFIX}-{YYYY}{SEQ:05d}")
    await db_session.commit()
