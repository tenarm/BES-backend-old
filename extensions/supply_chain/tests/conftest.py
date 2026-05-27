import sys
from pathlib import Path
import pytest

# Add core workspace directory to path to resolve core tests conftest
core_path = str(Path(__file__).resolve().parents[3] / "core")
if core_path not in sys.path:
    sys.path.append(core_path)

from tests.conftest import *  # Inherit and reuse all core fixtures
from fastapi import FastAPI
from core.database import get_async_session

# Import SupplyChain manifest so that SQLModel registers SupplyChain models before table creation
from supply_chain.manifest import manifest as supply_chain_manifest

@pytest.fixture
def test_app(db_session) -> FastAPI:
    """FastAPI app override for supply_chain extension tests, registering supply_chain manifest endpoints."""
    from core.router import router as auth_router
    
    app = FastAPI()
    app.include_router(auth_router)
    
    # Dynamically register the Supply Chain Manifest endpoints
    app.include_router(supply_chain_manifest.get_router())
    
    # Overwrite the db dependency
    async def override_get_async_session():
        yield db_session
    app.dependency_overrides[get_async_session] = override_get_async_session
    
    return app
