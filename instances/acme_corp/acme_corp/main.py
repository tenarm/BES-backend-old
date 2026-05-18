import os
import json
import importlib
import logging
from pathlib import Path
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlmodel import SQLModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─── 1. Bootstrap Configuration ───────────────────────────────────────────────
# Fix #3: All sys.path mutation, file I/O, and env injection is isolated inside
# _bootstrap_config() instead of running freely at module level. This makes the
# module safely importable in tests without side effects.
#
# Fix #2: Removed duplicate `from pathlib import Path` (was at both line 5 & 14).

def _bootstrap_config():
    """
    Reads the client onboarding config, resolves paths, and injects environment
    variables. Must be called before any core imports.

    Returns: (client_config dict, licensed_modules list, BASE_DIR Path)
    """
    import sys

    BASE_DIR = Path(__file__).resolve().parents[3]
    logger.info(f"BASE_DIR resolved to {BASE_DIR}")

    # Workspace members on sys.path (simulates editable installs in dev)
    core_path = str(BASE_DIR / "core")
    if core_path not in sys.path:
        sys.path.insert(0, core_path)

    import os
    
    CONFIG_PATH = BASE_DIR / "instances" / "acme_corp" / "config" / "onboard_config.json"
    os.environ["ADMIN_PERMISSIONS_PATH"] = str(BASE_DIR / "instances" / "acme_corp" / "config" / "admin_permissions.json")
    
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)

    licensed_modules = config.get("licensed_modules", [])

    for mod in licensed_modules:
        ext_path = BASE_DIR / "extensions" / mod
        if ext_path.exists():
            ext_str = str(ext_path)
            if ext_str not in sys.path:
                sys.path.insert(0, ext_str)

    # Resolve database URL (SQLite relative → absolute)
    db_url = config.get("database_url", "sqlite+aiosqlite:///./default.db")
    if ":///" in db_url and not db_url.startswith("postgresql"):
        prefix, path = db_url.rsplit("///", 1)
        abs_path = str(BASE_DIR / path)
        Path(abs_path).parent.mkdir(parents=True, exist_ok=True)
        db_url = f"{prefix}///{abs_path}"

    os.environ["DATABASE_URL"] = db_url
    os.environ.setdefault("DEBUG", "true")
    os.environ.setdefault(
        "JWT_SECRET_KEY",
        "dev-only-secret-change-in-production-" + config.get("client_id", "default")
    )

    return config, licensed_modules, BASE_DIR


CLIENT_CONFIG, LICENSED_MODULES, BASE_DIR = _bootstrap_config()


# ─── 2. Core Imports (safe after env vars are set) ────────────────────────────
from core.database import get_engine, get_async_session          # noqa: E402
from core.responses import setup_exception_handlers              # noqa: E402
from core.router import (                                         # noqa: E402
    router as auth_router,
    audit_router,
    seed_admin_user,
    seed_roles,
    cleanup_expired_tokens,
)
from core.middleware import (                                     # noqa: E402
    RequestLoggingMiddleware,
    ContextAwareSecurityMiddleware,
)
from core.auth import get_current_user                           # noqa: E402
from core.models import User                                     # noqa: E402
from core.rbac import get_simplified_json                        # noqa: E402


# ─── 3. Single-Pass Manifest Discovery ───────────────────────────────────────
# Fix #4: Previously two separate loops each called importlib.import_module()
# for manifests (once for models, once for routers). Now we discover all
# manifests once here, store the objects, and reuse them in both the lifespan
# (models + events) and route registration below.

_MODULE_MANIFESTS: dict[str, object | None] = {}

for _mod_name in LICENSED_MODULES:
    try:
        _manifest_mod = importlib.import_module(f"{_mod_name}.manifest")
        if hasattr(_manifest_mod, "manifest"):
            _MODULE_MANIFESTS[_mod_name] = _manifest_mod.manifest
            logger.info(f"Discovered manifest: {_mod_name}")
            continue
    except ImportError:
        pass
    # Legacy module (no manifest) — will use direct model/router import fallback
    _MODULE_MANIFESTS[_mod_name] = None
    logger.debug(f"No manifest found for {_mod_name}, will use legacy fallback")


# ─── 4. Lifespan ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = get_engine()

    # Always ensure core models are registered
    from core import models as _core_models  # noqa: F401

    # Register models and event handlers using pre-loaded manifests
    for mod_name, manifest in _MODULE_MANIFESTS.items():
        if manifest:
            manifest.get_models()  # Force SQLModel class registration
            logger.info(f"Loaded models (manifest): {mod_name}")

            handler_registrar = manifest.get_event_handlers()
            if handler_registrar and callable(handler_registrar):
                handler_registrar()
                logger.info(f"Registered event handlers: {mod_name}")
        else:
            # Legacy fallback
            try:
                importlib.import_module(f"{mod_name}.models")
                logger.info(f"Loaded models (legacy): {mod_name}")
            except ImportError as e:
                logger.warning(f"Could not load models for {mod_name}: {e}")

    # Create tables for all registered models
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # Seed & cleanup in one session block
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker as sa_sessionmaker
    session_maker = sa_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        await seed_roles(session)
        await seed_admin_user(session)
        await cleanup_expired_tokens(session)  # Fix #14: purge stale tokens on boot

    yield


# ─── 5. App Initialization ────────────────────────────────────────────────────
app = FastAPI(
    title=CLIENT_CONFIG.get("client_name", "BES"),
    lifespan=lifespan,
    version="0.1.0",
)

# Fix #11: CORS origins read from client config with safe localhost defaults.
CORS_ORIGINS: list[str] = CLIENT_CONFIG.get("cors_origins", [
    "http://localhost:4200",
    "http://127.0.0.1:4200",
    "http://localhost:3000",
    "http://localhost:5173",
])

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(ContextAwareSecurityMiddleware)

setup_exception_handlers(app)

# Core routers
app.include_router(auth_router)
app.include_router(audit_router)   # Fix #10: audit now at /api/v1/audit/*


# ─── 6. Dynamic Route Registration (single-pass, reuses discovered manifests) ─
for _mod_name, _manifest in _MODULE_MANIFESTS.items():
    if _manifest:
        app.include_router(_manifest.get_router())
        logger.info(f"Registered router (manifest): {_mod_name}")
    else:
        # Legacy fallback
        try:
            _router_mod = importlib.import_module(f"{_mod_name}.router")
            if hasattr(_router_mod, "router"):
                app.include_router(_router_mod.router)
                logger.info(f"Registered router (legacy): {_mod_name}")
        except ImportError as e:
            logger.warning(f"Could not load router for {_mod_name}: {e}")


# ─── 7. Health Check ──────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "client": CLIENT_CONFIG.get("client_name"),
        "version": "0.1.0",
        "modules_loaded": len(LICENSED_MODULES),
    }


# ─── 8. Bootstrap Endpoint ────────────────────────────────────────────────────
@app.get("/api/v1/bootstrap")
async def bootstrap(user: User = Depends(get_current_user)):
    """
    Returns the client configuration and the authenticated user's permissions,
    filtered to only the licensed modules for this client instance.
    """
    user_perms = get_simplified_json(user, licensed_modules=LICENSED_MODULES)

    return {
        "status": "success",
        "data": {
            "client_name": CLIENT_CONFIG.get("client_name"),
            "active_modules": LICENSED_MODULES,
            "user_id": str(user.id),
            "username": user.username,
            "permissions": user_perms["permissions"],
        }
    }
