import importlib
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ─── 1. Bootstrap Configuration (Must be imported first) ──────────────────────
from msme_pro.bootstrap import CLIENT_CONFIG, LICENSED_MODULES

# ─── 2. Core Imports ────────────────────────────────────────────────────────
from core.responses import setup_exception_handlers
from core.router import (
    router as auth_router,
    audit_router,
    notification_router,
)
from core.middleware import (
    RequestLoggingMiddleware,
    ContextAwareSecurityMiddleware,
)

# ─── 3. Instance Modules ────────────────────────────────────────────────────
from msme_pro.manifests import _MODULE_MANIFESTS
from msme_pro.lifespan import lifespan
from msme_pro.api.endpoints import router as endpoints_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── 4. App Initialization ────────────────────────────────────────────────────
app = FastAPI(
    title=CLIENT_CONFIG.get("client_name", "BES"),
    lifespan=lifespan,
    version="0.1.0",
)

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
app.include_router(audit_router)
app.include_router(notification_router)

# Instance standalone endpoints
app.include_router(endpoints_router)


# ─── 5. Dynamic Route Registration ────────────────────────────────────────────
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
