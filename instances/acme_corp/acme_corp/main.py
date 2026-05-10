import os
import json
import importlib
import logging
from pathlib import Path
from fastapi import FastAPI
from contextlib import asynccontextmanager
from sqlmodel import SQLModel

logger = logging.getLogger(__name__)

import sys
from pathlib import Path

# --- 1. Load Onboarding Configuration ---
BASE_DIR = Path(__file__).resolve().parents[3]
print(f"DEBUG: BASE_DIR resolved to {BASE_DIR}")

# Automatically add workspace members to sys.path for development
# We use insert(0) to ensure these take priority
for path in [BASE_DIR / "core", BASE_DIR / "extensions/sales", BASE_DIR / "extensions/finance"]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
        print(f"DEBUG: Added to sys.path: {path}")

CONFIG_PATH = BASE_DIR / "onboarded" / "acme_corp.json"

with open(CONFIG_PATH, "r") as f:
    client_config = json.load(f)

# Set the database URL for the core engine to pick up BEFORE importing core
os.environ["DATABASE_URL"] = client_config.get("database_url", "sqlite+aiosqlite:///./default.db")

# Now safe to import core components
from core.database import engine, get_async_session
from core.responses import setup_exception_handlers
from core.router import router as auth_router, seed_admin_user

LICENSED_MODULES = client_config.get("licensed_modules", [])

# --- 2. Dynamic Bootstrapper Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Always load core models
    from core import models as core_models
    
    # Dynamically import models for licensed modules
    for module_name in LICENSED_MODULES:
        try:
            importlib.import_module(f"{module_name}.models")
            logger.info(f"Loaded models for licensed module: {module_name}")
        except ImportError as e:
            logger.warning(f"Could not load models for {module_name}: {e}")

    # Create tables only for the loaded models (requires run_sync for async engine)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    # Seed Admin User
    async with engine.begin() as conn:
        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy.orm import sessionmaker
        async_session_maker = sessionmaker(conn, class_=AsyncSession, expire_on_commit=False)
        async with async_session_maker() as session:
            await seed_admin_user(session)
        
    yield

from fastapi.middleware.cors import CORSMiddleware

# --- 3. App Initialization ---
app = FastAPI(title=client_config.get("client_name", "Dynamic ERP"), lifespan=lifespan)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_exception_handlers(app)
app.include_router(auth_router)

# --- 4. Dynamic Route Gathering ---
for module_name in LICENSED_MODULES:
    try:
        module_router = importlib.import_module(f"{module_name}.router")
        if hasattr(module_router, "router"):
            app.include_router(module_router.router)
            logger.info(f"Registered router for module: {module_name}")
    except ImportError as e:
        logger.warning(f"Could not load router for {module_name}: {e}")

# --- 5. Dynamic Bootstrap Endpoint ---
@app.get("/api/v1/bootstrap")
def bootstrap():
    from core.rbac import get_simplified_json
    
    full_json = get_simplified_json("user_123")
    
    # Filter permissions to ONLY include licensed modules
    filtered_permissions = {
        k: v for k, v in full_json["permissions"].items()
        if any(k.startswith(f"{mod}_") for mod in LICENSED_MODULES)
    }
    
    return {
        "status": "success",
        "data": {
            "client_name": client_config.get("client_name"),
            "active_modules": LICENSED_MODULES,
            "permissions": filtered_permissions
        }
    }
