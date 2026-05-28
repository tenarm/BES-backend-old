import os
import logging
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import User, Role, RefreshToken
from ..auth import get_password_hash
from ..rbac import PERMISSIONS_SCHEMA

logger = logging.getLogger(__name__)


async def seed_roles(session: AsyncSession):
    """Seeds default roles if they don't exist."""
    roles_to_seed = [
        {
            "name": "admin",
            "description": "Full administrative access to all modules and actions",
            "permissions": PERMISSIONS_SCHEMA
        }
    ]

    for role_data in roles_to_seed:
        stmt = select(Role).where(Role.name == role_data["name"])
        result = await session.execute(stmt)
        if not result.scalars().first():
            role = Role(**role_data)
            session.add(role)
            logger.info(f"Seeded role: {role_data['name']}")

    await session.commit()


async def seed_admin_user(session: AsyncSession):
    """
    Seeds an admin user if none exists.
    Password is sourced from INITIAL_ADMIN_PASSWORD env var.
    Falls back to 'admin123' ONLY in development (when DEBUG=true).
    """
    stmt = select(User).where(User.username == "admin")
    result = await session.execute(stmt)
    if result.scalars().first():
        return  # Admin already exists

    admin_password = os.environ.get("INITIAL_ADMIN_PASSWORD")
    is_debug = os.getenv("DEBUG", "false").lower() == "true"

    if not admin_password:
        if is_debug:
            admin_password = "admin123"
            logger.warning("DEBUG MODE: Using default admin password 'admin123'. DO NOT use in production.")
        else:
            logger.info("No INITIAL_ADMIN_PASSWORD set and DEBUG is off. Skipping admin seed.")
            return

    # Find the admin role
    role_stmt = select(Role).where(Role.name == "admin")
    role_result = await session.execute(role_stmt)
    admin_role = role_result.scalars().first()

    admin = User(
        username="admin",
        email="admin@bes.com",
        hashed_password=get_password_hash(admin_password),
        full_name="System Administrator",
        is_superuser=True,
        role_id=admin_role.id if admin_role else None
    )
    session.add(admin)
    await session.commit()
    logger.info("Seeded admin user")


async def cleanup_expired_tokens(session: AsyncSession) -> int:
    """
    Fix #14: Purges revoked and expired RefreshToken rows.

    RefreshToken rows accumulate indefinitely without cleanup. Call this
    from the instance lifespan (e.g., on startup or via a scheduler) to
    keep the table lean and revocation checks fast.

    Returns the number of rows deleted.
    """
    from sqlalchemy import delete as sa_delete
    from datetime import datetime, timezone

    cutoff = datetime.now(timezone.utc)
    stmt = sa_delete(RefreshToken).where(
        (RefreshToken.is_revoked == True) |  # noqa: E712
        (RefreshToken.expires_at < cutoff)
    )
    result = await session.execute(stmt)
    await session.commit()
    deleted = result.rowcount
    if deleted:
        logger.info(f"[TokenCleanup] Purged {deleted} expired/revoked refresh tokens.")
    return deleted
