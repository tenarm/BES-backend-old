import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from .database import get_async_session
from .models import User, Role, RefreshToken

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration — fail-fast on missing secrets
# ---------------------------------------------------------------------------
# The secret is read once from the environment and cached to avoid repeated
# os.environ lookups on every token creation and decode call.
_JWT_SECRET: str | None = None


def _get_secret_key() -> str:
    global _JWT_SECRET
    if _JWT_SECRET is None:
        key = os.environ.get("JWT_SECRET_KEY")
        if not key:
            raise RuntimeError(
                "FATAL: JWT_SECRET_KEY environment variable is not set. "
                "Set it to a strong, random secret before starting the server."
            )
        _JWT_SECRET = key
    return _JWT_SECRET


ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Returns True if the plain-text password matches the stored bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Returns a bcrypt hash of the given plain-text password."""
    return pwd_context.hash(password)


# ---------------------------------------------------------------------------
# JWT token management
# ---------------------------------------------------------------------------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a short-lived JWT access token.

    Args:
        data:          Payload claims (must include 'sub' = username).
        expires_delta: Custom TTL. Defaults to ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        Signed JWT string.
    """
    secret = _get_secret_key()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, secret, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> tuple[str, datetime]:
    """
    Creates a long-lived JWT refresh token.

    Each refresh token includes a unique 'jti' claim for revocation tracking.

    Returns:
        (token_string, expiry_datetime)
    """
    secret = _get_secret_key()
    to_encode = data.copy()
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({
        "exp": expires_at,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
    })
    token = jwt.encode(to_encode, secret, algorithm=ALGORITHM)
    return token, expires_at


def decode_token(token: str) -> dict:
    """
    Decodes and validates a JWT token.

    Raises:
        jose.JWTError: If the token is expired, tampered, or otherwise invalid.
    """
    secret = _get_secret_key()
    return jwt.decode(token, secret, algorithms=[ALGORITHM])


# ---------------------------------------------------------------------------
# FastAPI dependency: current user resolver
# ---------------------------------------------------------------------------

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_async_session)
) -> User:
    """
    FastAPI dependency that validates the JWT access token and returns the active User.

    Eagerly loads the user's Role.permissions and caches them on ``user._cached_permissions``
    so that ``require_permission`` and ``get_user_permissions`` work for all non-superusers
    without issuing additional DB queries on every RBAC check within the same request.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise credentials_exception
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    stmt = select(User).where(User.username == username, User.is_active == True)
    result = await session.execute(stmt)
    user = result.scalars().first()

    if user is None:
        raise credentials_exception

    # Eagerly resolve and cache permissions for this request.
    # Superusers receive the full schema; regular users receive their Role's
    # permissions merged with any per-user custom overrides.
    if not user.is_superuser:
        from .rbac import deep_merge_permissions
        role_perms: dict = {}
        if user.role_id is not None:
            role_stmt = select(Role).where(Role.id == user.role_id)
            role_result = await session.execute(role_stmt)
            role = role_result.scalars().first()
            if role:
                role_perms = role.permissions

        user_custom_perms: dict = getattr(user, "custom_permissions", {}) or {}
        user._cached_permissions = deep_merge_permissions(role_perms, user_custom_perms)

    return user
