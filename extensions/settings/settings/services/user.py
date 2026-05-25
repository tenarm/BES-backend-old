import logging
import uuid
import secrets
import hashlib
from datetime import datetime
from typing import List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from core.repository import BaseRepository
from core.exceptions import ConcurrencyError
from core.models import User, Role, RefreshToken
from core.auth import get_password_hash
from core.events import event_bus, BaseEventPayload

from ..models.user import UserSubsidiaryAccess, SSOConfiguration, APIKey
from ..schemas.user import (
    UserCreate, UserUpdate,
    RoleCreate, RoleUpdate,
    SSOConfigCreate, APIKeyCreate
)

logger = logging.getLogger(__name__)

# --- Repository Instances ---
user_repo = BaseRepository(User)
role_repo = BaseRepository(Role)
refresh_repo = BaseRepository(RefreshToken)
user_sub_repo = BaseRepository(UserSubsidiaryAccess)
sso_repo = BaseRepository(SSOConfiguration)
api_key_repo = BaseRepository(APIKey)

# --- Domain Exceptions ---
class DomainException(Exception):
    """Base domain exception for settings operations."""
    pass

class LastAdminDeactivationError(DomainException):
    """Raised when trying to deactivate or delete the last administrator user."""
    pass

class SelfDeactivationError(DomainException):
    """Raised when a user attempts to deactivate or lock themselves."""
    pass

class WeakPasswordError(DomainException):
    """Raised when a password fails complexity requirements."""
    pass

class DuplicateRoleNameError(DomainException):
    """Raised when a role name is already registered."""
    pass

class RoleAssignedToUsersError(DomainException):
    """Raised when attempting to delete a role still in use."""
    pass

# --- Helper Password Validation ---
def validate_password_strength(password: str, username: str, email: str) -> None:
    """
    Validates that the password meets security strength policies:
    - 12+ characters long
    - At least 1 uppercase letter, 1 lowercase letter, 1 digit, 1 special character
    - Does not contain the username or email
    """
    if len(password) < 12:
        raise WeakPasswordError("Password must be at least 12 characters long.")
    if not any(c.isupper() for c in password):
        raise WeakPasswordError("Password must contain at least one uppercase letter.")
    if not any(c.islower() for c in password):
        raise WeakPasswordError("Password must contain at least one lowercase letter.")
    if not any(c.isdigit() for c in password):
        raise WeakPasswordError("Password must contain at least one numeric digit.")
    if not any(c in "!@#$%^&*()-_=+[]{}|;:',.<>?/`~" for c in password):
        raise WeakPasswordError("Password must contain at least one special character.")
    if username.lower() in password.lower() or (email and email.split('@')[0].lower() in password.lower()):
        raise WeakPasswordError("Password cannot contain the username or email address.")

# --- User Service ---
class UserService:
    @staticmethod
    async def list_users(session: AsyncSession, search: Optional[str] = None, is_active: Optional[bool] = None, page: int = 1, page_size: int = 50) -> tuple[List[User], int]:
        """
        Lists users with search, status filters, and pagination.
        """
        stmt = select(User).where(User.is_deleted == False)
        
        if search:
            stmt = stmt.where(
                User.username.like(f"%{search}%") | 
                User.email.like(f"%{search}%") | 
                User.full_name.like(f"%{search}%")
            )
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)
            
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await session.execute(count_stmt)).scalar() or 0
        
        offset = (page - 1) * page_size
        stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(page_size)
        res = await session.execute(stmt)
        users = res.scalars().all()
        
        # Attach allowed subsidiary IDs to each user
        for user in users:
            sub_stmt = select(UserSubsidiaryAccess.subsidiary_id).where(
                UserSubsidiaryAccess.user_id == user.id,
                UserSubsidiaryAccess.is_deleted == False
            )
            sub_res = await session.execute(sub_stmt)
            object.__setattr__(user, 'allowed_subsidiary_ids', list(sub_res.scalars().all()))
            
        return list(users), total

    @staticmethod
    async def get_user(session: AsyncSession, id: uuid.UUID) -> Optional[User]:
        """
        Retrieves a single user profile including allowed subsidiaries.
        """
        user = await user_repo.get(session, id)
        if not user:
            return None
            
        sub_stmt = select(UserSubsidiaryAccess.subsidiary_id).where(
            UserSubsidiaryAccess.user_id == id,
            UserSubsidiaryAccess.is_deleted == False
        )
        sub_res = await session.execute(sub_stmt)
        object.__setattr__(user, 'allowed_subsidiary_ids', list(sub_res.scalars().all()))
        return user

    @staticmethod
    async def create_user(session: AsyncSession, data: UserCreate) -> User:
        """
        Registers a new user, checks username/email uniqueness, hashes password, 
        and registers subsidiary roaming mappings.
        """
        name_stmt = select(User).where(User.username == data.username, User.is_deleted == False)
        if (await session.execute(name_stmt)).scalars().first():
            raise ValueError(f"Username '{data.username}' is already in use.")
            
        email_stmt = select(User).where(User.email == data.email, User.is_deleted == False)
        if (await session.execute(email_stmt)).scalars().first():
            raise ValueError(f"Email '{data.email}' is already in use.")
            
        if data.role_id:
            role = await role_repo.get(session, data.role_id)
            if not role:
                raise ValueError(f"Role with ID {data.role_id} does not exist.")

        validate_password_strength(data.password, data.username, data.email)

        user_obj = User(
            username=data.username,
            email=data.email,
            full_name=data.full_name,
            hashed_password=get_password_hash(data.password),
            role_id=data.role_id,
            subsidiary_id=data.primary_subsidiary_id,
            is_active=True,
            is_superuser=False
        )
        db_user = await user_repo.create(session, user_obj)
        
        allowed_ids = data.allowed_subsidiary_ids or []
        if data.primary_subsidiary_id and uuid.UUID(data.primary_subsidiary_id) not in allowed_ids:
            allowed_ids.append(uuid.UUID(data.primary_subsidiary_id))
            
        for sub_id in allowed_ids:
            access = UserSubsidiaryAccess(user_id=db_user.id, subsidiary_id=sub_id)
            session.add(access)
            
        await session.commit()
        await session.refresh(db_user)
        
        object.__setattr__(db_user, 'allowed_subsidiary_ids', allowed_ids)
        
        event = BaseEventPayload(
            emitter_module="settings",
            event_type="USER_CREATED",
            data={
                "user_id": str(db_user.id),
                "username": db_user.username,
                "email": db_user.email,
                "primary_subsidiary_id": db_user.subsidiary_id
            }
        )
        await event_bus.emit(event)
        return db_user

    @staticmethod
    async def update_user(session: AsyncSession, id: uuid.UUID, data: UserUpdate, version_id: int) -> User:
        """
        Updates user profile, role, primary subsidiary, and subsidiary bindings.
        Applies optimistic concurrency conflict checks.
        """
        db_user = await user_repo.get(session, id)
        if not db_user:
            raise ValueError(f"User with ID {id} not found.")

        if data.email is not None and data.email != db_user.email:
            email_stmt = select(User).where(User.email == data.email, User.is_deleted == False)
            if (await session.execute(email_stmt)).scalars().first():
                raise ValueError(f"Email '{data.email}' is already in use.")

        if data.role_id is not None:
            role = await role_repo.get(session, data.role_id)
            if not role:
                raise ValueError(f"Role with ID {data.role_id} does not exist.")

        if data.allowed_subsidiary_ids is not None:
            del_stmt = select(UserSubsidiaryAccess).where(
                UserSubsidiaryAccess.user_id == id,
                UserSubsidiaryAccess.is_deleted == False
            )
            old_accesses = (await session.execute(del_stmt)).scalars().all()
            for acc in old_accesses:
                acc.is_deleted = True
                session.add(acc)
                
            for sub_id in data.allowed_subsidiary_ids:
                access = UserSubsidiaryAccess(user_id=id, subsidiary_id=sub_id)
                session.add(access)

        update_dict = data.model_dump(exclude={"allowed_subsidiary_ids"}, exclude_unset=True)
        if "primary_subsidiary_id" in update_dict:
            update_dict["subsidiary_id"] = update_dict.pop("primary_subsidiary_id")
        update_dict["version_id"] = version_id
        updated_user = await user_repo.update(session, db_user, update_dict)
        
        await session.commit()
        await session.refresh(updated_user)
        
        sub_stmt = select(UserSubsidiaryAccess.subsidiary_id).where(
            UserSubsidiaryAccess.user_id == id,
            UserSubsidiaryAccess.is_deleted == False
        )
        sub_res = await session.execute(sub_stmt)
        object.__setattr__(updated_user, 'allowed_subsidiary_ids', list(sub_res.scalars().all()))
        
        event = BaseEventPayload(
            emitter_module="settings",
            event_type="USER_UPDATED",
            data={
                "user_id": str(updated_user.id),
                "username": updated_user.username
            }
        )
        await event_bus.emit(event)
        return updated_user

    @staticmethod
    async def update_user_status(session: AsyncSession, id: uuid.UUID, is_active: bool, actor_id: uuid.UUID) -> User:
        """
        Updates user active status. Deactivating a user uses pessimistic locks 
        and revokes all active session refresh tokens.
        """
        if id == actor_id:
            raise SelfDeactivationError("You cannot modify your own active status.")

        db_user = await user_repo.get_with_lock(session, id)
        if not db_user:
            raise ValueError(f"User with ID {id} not found.")

        if not is_active:
            admin_role_stmt = select(Role.id).where(Role.name == "admin")
            admin_role_id = (await session.execute(admin_role_stmt)).scalar()
            
            count_stmt = select(func.count(User.id)).where(
                User.is_active == True,
                User.is_deleted == False,
                (User.is_superuser == True) | (User.role_id == admin_role_id)
            )
            active_admins = (await session.execute(count_stmt)).scalar() or 0
            
            is_target_admin = db_user.is_superuser or (admin_role_id and db_user.role_id == admin_role_id)
            if is_target_admin and active_admins <= 1:
                raise LastAdminDeactivationError("Cannot deactivate the last active administrator.")

            token_stmt = select(RefreshToken).where(
                RefreshToken.user_id == id,
                RefreshToken.is_revoked == False
            )
            tokens = (await session.execute(token_stmt)).scalars().all()
            for tok in tokens:
                tok.is_revoked = True
                session.add(tok)

        db_user.is_active = is_active
        session.add(db_user)
        await session.commit()
        await session.refresh(db_user)

        if not is_active:
            event = BaseEventPayload(
                emitter_module="settings",
                event_type="USER_DEACTIVATED",
                data={
                    "user_id": str(id),
                    "deactivator_id": str(actor_id)
                }
            )
            await event_bus.emit(event)
        return db_user

    @staticmethod
    async def reset_password(session: AsyncSession, id: uuid.UUID, new_password: str) -> None:
        """
        Resets a user's password, invalidates all active sessions.
        """
        db_user = await user_repo.get_with_lock(session, id)
        if not db_user:
            raise ValueError(f"User with ID {id} not found.")

        validate_password_strength(new_password, db_user.username, db_user.email)

        db_user.hashed_password = get_password_hash(new_password)
        session.add(db_user)

        token_stmt = select(RefreshToken).where(
            RefreshToken.user_id == id,
            RefreshToken.is_revoked == False
        )
        tokens = (await session.execute(token_stmt)).scalars().all()
        for tok in tokens:
            tok.is_revoked = True
            session.add(tok)

        await session.commit()

# --- Role Service ---
class RoleService:
    @staticmethod
    async def list_roles(session: AsyncSession, page: int = 1, page_size: int = 50) -> tuple[List[Role], int]:
        stmt = select(Role).where(Role.is_deleted == False)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await session.execute(count_stmt)).scalar() or 0
        
        offset = (page - 1) * page_size
        stmt = stmt.order_by(Role.name.asc()).offset(offset).limit(page_size)
        roles = (await session.execute(stmt)).scalars().all()
        return list(roles), total

    @staticmethod
    async def get_role(session: AsyncSession, id: uuid.UUID) -> Optional[Role]:
        return await role_repo.get(session, id)

    @staticmethod
    async def create_role(session: AsyncSession, data: RoleCreate) -> Role:
        stmt = select(Role).where(Role.name == data.name, Role.is_deleted == False)
        if (await session.execute(stmt)).scalars().first():
            raise DuplicateRoleNameError(f"Role name '{data.name}' is already in use.")

        obj = Role(
            name=data.name,
            description=data.description,
            permissions=data.permissions
        )
        db_role = await role_repo.create(session, obj)
        await session.commit()
        
        event = BaseEventPayload(
            emitter_module="settings",
            event_type="ROLE_PERMISSIONS_UPDATED",
            data={"role_id": str(db_role.id)}
        )
        await event_bus.emit(event)
        return db_role

    @staticmethod
    async def update_role(session: AsyncSession, id: uuid.UUID, data: RoleUpdate, version_id: int) -> Role:
        db_role = await role_repo.get(session, id)
        if not db_role:
            raise ValueError(f"Role with ID {id} not found.")

        update_dict = data.model_dump(exclude_unset=True)
        update_dict["version_id"] = version_id
        
        updated_role = await role_repo.update(session, db_role, update_dict)
        await session.commit()

        event = BaseEventPayload(
            emitter_module="settings",
            event_type="ROLE_PERMISSIONS_UPDATED",
            data={"role_id": str(updated_role.id)}
        )
        await event_bus.emit(event)
        return updated_role

    @staticmethod
    async def delete_role(session: AsyncSession, id: uuid.UUID) -> None:
        db_role = await role_repo.get(session, id)
        if not db_role:
            raise ValueError(f"Role with ID {id} not found.")

        if db_role.name in ["admin", "manager", "staff"]:
            raise ValueError("Standard system roles cannot be deleted.")

        user_stmt = select(User).where(User.role_id == id, User.is_deleted == False, User.is_active == True)
        assigned_user = (await session.execute(user_stmt)).scalars().first()
        if assigned_user:
            raise RoleAssignedToUsersError("Cannot delete role while it is still assigned to active users.")

        db_role.is_deleted = True
        session.add(db_role)
        await session.commit()

# --- API Key Service ---
class APIKeyService:
    @staticmethod
    async def generate_key(session: AsyncSession, name: str, service_user_id: uuid.UUID, expires_at: Optional[datetime] = None) -> tuple[APIKey, str]:
        """
        Generates a new API Key mapping to a Service Account User.
        Hashes key for storage and returns plaintext key once.
        """
        user = await user_repo.get(session, service_user_id)
        if not user or not user.is_active or user.is_deleted:
            raise ValueError("Service user account does not exist or is inactive.")

        prefix = "bes_live_"
        secret = secrets.token_hex(32)
        plaintext_key = f"{prefix}{secret}"

        hashed = hashlib.sha256(plaintext_key.encode('utf-8')).hexdigest()

        key_obj = APIKey(
            name=name,
            key_prefix=prefix,
            hashed_key=hashed,
            user_id=service_user_id,
            expires_at=expires_at,
            is_active=True
        )
        db_key = await api_key_repo.create(session, key_obj)
        await session.commit()

        return db_key, plaintext_key

    @staticmethod
    async def revoke_key(session: AsyncSession, id: uuid.UUID) -> None:
        db_key = await api_key_repo.get(session, id)
        if not db_key:
            raise ValueError(f"API key with ID {id} not found.")

        db_key.is_active = False
        db_key.is_deleted = True
        session.add(db_key)
        await session.commit()
        
        event = BaseEventPayload(
            emitter_module="settings",
            event_type="API_KEY_REVOKED",
            data={"api_key_id": str(id)}
        )
        await event_bus.emit(event)

# --- SSO Configuration Service ---
class SSOConfigurationService:
    @staticmethod
    async def get_config(session: AsyncSession) -> Optional[SSOConfiguration]:
        stmt = select(SSOConfiguration).where(SSOConfiguration.is_deleted == False)
        res = await session.execute(stmt)
        return res.scalars().first()

    @staticmethod
    async def save_config(session: AsyncSession, data: SSOConfigCreate) -> SSOConfiguration:
        stmt = select(SSOConfiguration).where(SSOConfiguration.is_deleted == False)
        existing = (await session.execute(stmt)).scalars().first()
        
        if existing:
            update_dict = data.model_dump()
            updated = await sso_repo.update(session, existing, update_dict)
            await session.commit()
            return updated
        else:
            obj = SSOConfiguration.model_validate(data)
            new_config = await sso_repo.create(session, obj)
            await session.commit()
            return new_config
