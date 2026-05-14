import os
import json
import importlib
import logging
from pathlib import Path
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlmodel import SQLModel

logger = logging.getLogger(__name__)

import sys
from pathlib import Path

# --- 1. Load Onboarding Configuration ---
BASE_DIR = Path(__file__).resolve().parents[3]
logger.info(f"BASE_DIR resolved to {BASE_DIR}")

# Automatically add workspace members to sys.path for development
sys.path.insert(0, str(BASE_DIR / "core"))

# Load config to get licensed modules early for sys.path
CONFIG_PATH = BASE_DIR / "onboarded" / "acme_corp.json"
with open(CONFIG_PATH, "r") as f:
    client_config = json.load(f)
    LICENSED_MODULES = client_config.get("licensed_modules", [])

for mod in LICENSED_MODULES:
    ext_path = BASE_DIR / "extensions" / mod
    if ext_path.exists():
        sys.path.insert(0, str(ext_path))

# Set environment variables BEFORE importing core
# Resolve the database path to an absolute path relative to BASE_DIR
db_url = client_config.get("database_url", "sqlite+aiosqlite:///./default.db")
if ":///" in db_url and not db_url.startswith("postgresql"):
    # For SQLite, resolve relative paths to absolute
    prefix, path = db_url.rsplit("///", 1)
    abs_path = str(BASE_DIR / path)
    # Ensure the data directory exists
    Path(abs_path).parent.mkdir(parents=True, exist_ok=True)
    db_url = f"{prefix}///{abs_path}"

os.environ["DATABASE_URL"] = db_url

# Set DEBUG for dev mode (enables fallback admin password)
os.environ.setdefault("DEBUG", "true")

# Set JWT secret for development (MUST be overridden in production)
os.environ.setdefault("JWT_SECRET_KEY", "dev-only-secret-change-in-production-" + client_config.get("client_id", "default"))

# Now safe to import core components
from core.database import get_engine, get_async_session
from core.responses import setup_exception_handlers
from core.router import router as auth_router, seed_admin_user, seed_roles
from core.middleware import RequestLoggingMiddleware, ContextAwareSecurityMiddleware
from core.auth import get_current_user
from core.models import User
from core.rbac import get_simplified_json


# --- 2. Dynamic Bootstrapper Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine()

    # Always load core models
    from core import models as core_models

    # Dynamically import models for licensed modules
    # Try manifest first, fall back to legacy import
    for module_name in LICENSED_MODULES:
        try:
            # Try new manifest-based loading
            manifest_mod = importlib.import_module(f"{module_name}.manifest")
            if hasattr(manifest_mod, "manifest"):
                manifest = manifest_mod.manifest
                manifest.get_models()  # Force model class registration
                logger.info(f"Loaded manifest for module: {module_name}")

                # Register event handlers
                handler_registrar = manifest.get_event_handlers()
                if handler_registrar and callable(handler_registrar):
                    handler_registrar()
                    logger.info(f"Registered event handlers for module: {module_name}")
                continue
        except ImportError:
            pass

        # Legacy fallback: direct importlib
        try:
            importlib.import_module(f"{module_name}.models")
            logger.info(f"Loaded models (legacy) for module: {module_name}")
        except ImportError as e:
            logger.warning(f"Could not load models for {module_name}: {e}")

    # Create tables for all loaded models
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # Seed roles and admin user
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session_maker() as session:
        await seed_roles(session)
        await seed_admin_user(session)

    yield


# --- 3. App Initialization ---
app = FastAPI(
    title=client_config.get("client_name", "Dynamic BES"),
    lifespan=lifespan,
    version="0.1.0"
)

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

# Custom Middleware
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(ContextAwareSecurityMiddleware)

# Exception Handlers
setup_exception_handlers(app)

# Core Auth Routes
app.include_router(auth_router)


# --- 4. Dynamic Route Gathering ---
for module_name in LICENSED_MODULES:
    try:
        # Try manifest first
        manifest_mod = importlib.import_module(f"{module_name}.manifest")
        if hasattr(manifest_mod, "manifest"):
            app.include_router(manifest_mod.manifest.get_router())
            logger.info(f"Registered router (manifest) for module: {module_name}")
            continue
    except ImportError:
        pass

    # Legacy fallback
    try:
        module_router = importlib.import_module(f"{module_name}.router")
        if hasattr(module_router, "router"):
            app.include_router(module_router.router)
            logger.info(f"Registered router (legacy) for module: {module_name}")
    except ImportError as e:
        logger.warning(f"Could not load router for {module_name}: {e}")


# --- 5. Health Check (unauthenticated) ---
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "client": client_config.get("client_name"),
        "version": "0.1.0",
        "modules_loaded": len(LICENSED_MODULES)
    }


# --- 6. Bootstrap Endpoint (authenticated) ---
@app.get("/api/v1/bootstrap")
async def bootstrap(user: User = Depends(get_current_user)):
    """
    Returns the client configuration and the authenticated user's permissions.
    Filtered to only include licensed modules.
    """
    user_perms = get_simplified_json(user, licensed_modules=LICENSED_MODULES)

    return {
        "status": "success",
        "data": {
            "client_name": client_config.get("client_name"),
            "active_modules": LICENSED_MODULES,
            "user_id": str(user.id),
            "username": user.username,
            "permissions": user_perms["permissions"]
        }
    }
