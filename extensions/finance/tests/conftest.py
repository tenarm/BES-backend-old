import sys
from pathlib import Path

# Add core workspace directory to path to resolve core tests conftest
core_path = str(Path(__file__).resolve().parents[3] / "core")
if core_path not in sys.path:
    sys.path.append(core_path)

from tests.conftest import *  # Inherit and reuse all core fixtures
from fastapi import FastAPI
from core.database import get_async_session

@pytest.fixture
def test_app(db_session) -> FastAPI:
    """FastAPI app override for finance extension tests, registering finance manifest endpoints."""
    from finance.manifest import FinanceManifest
    from core.router import router as auth_router
    
    app = FastAPI()
    app.include_router(auth_router)
    
    # Dynamically register the Finance Manifest endpoints
    manifest = FinanceManifest()
    app.include_router(manifest.get_router())
    
    # Overwrite the db dependency
    async def override_get_async_session():
        yield db_session
    app.dependency_overrides[get_async_session] = override_get_async_session
    
    return app
