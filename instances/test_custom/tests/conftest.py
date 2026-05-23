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
    """FastAPI app override for instance integration testing, importing the client's actual main FastAPI app."""
    from test_custom.main import app as main_app
    
    # Overwrite the db dependency in the actual fused client app
    async def override_get_async_session():
        yield db_session
    main_app.dependency_overrides[get_async_session] = override_get_async_session
    
    return main_app
