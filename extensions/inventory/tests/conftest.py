import sys
import pytest
from pathlib import Path
from fastapi import FastAPI

# Resolve the core path to inherit standard database/client overrides
core_path = str(Path(__file__).resolve().parents[3] / "core")
if core_path not in sys.path:
    sys.path.append(core_path)

from tests.conftest import *
from core.database import get_async_session

@pytest.fixture
def test_app(db_session) -> FastAPI:
    """App fixture containing core routers + the extension under test."""
    from inventory.manifest import manifest
    app = FastAPI()
    
    # Register extension router dynamically
    app.include_router(manifest.get_router())
    
    # Override DB dependencies
    async def override_get_async_session():
        yield db_session
    app.dependency_overrides[get_async_session] = override_get_async_session
    return app
