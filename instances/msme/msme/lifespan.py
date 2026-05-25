import importlib
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlmodel import SQLModel

from core.database import get_engine
from core.router import seed_admin_user, seed_roles, cleanup_expired_tokens

from msme.manifests import _MODULE_MANIFESTS

logger = logging.getLogger(__name__)

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
