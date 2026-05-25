import pytest
import uuid
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import User, Role, RefreshToken
from settings.models import UserSubsidiaryAccess, SSOConfiguration, APIKey
from settings.schemas import UserCreate, UserUpdate, RoleCreate, RoleUpdate, SSOConfigCreate, APIKeyCreate
from settings.services import (
    UserService, RoleService, APIKeyService, SSOConfigurationService,
    SelfDeactivationError, LastAdminDeactivationError, WeakPasswordError,
    DuplicateRoleNameError, RoleAssignedToUsersError
)

@pytest.mark.asyncio
async def test_create_user_success(db_session: AsyncSession):
    # 1. Create a primary subsidiary mock (or use empty string)
    sub_id = str(uuid.uuid4())
    
    # 2. Provision new user
    user_in = UserCreate(
        username="john_doe",
        email="john@example.com",
        full_name="John Doe",
        password="SecurePass123!",
        primary_subsidiary_id=sub_id
    )
    user = await UserService.create_user(db_session, user_in)
    
    assert user.username == "john_doe"
    assert user.email == "john@example.com"
    assert user.hashed_password != "SecurePass123!"  # Password hashed
    assert user.is_active is True
    
    # Check subsidiary junction record
    stmt = select(UserSubsidiaryAccess).where(UserSubsidiaryAccess.user_id == user.id)
    res = await db_session.execute(stmt)
    accesses = res.scalars().all()
    assert len(accesses) == 1
    assert str(accesses[0].subsidiary_id) == sub_id

@pytest.mark.asyncio
async def test_create_user_duplicate_validation(db_session: AsyncSession):
    sub_id = str(uuid.uuid4())
    user_in = UserCreate(
        username="clara_smith",
        email="clara@example.com",
        full_name="Clara Smith",
        password="SecurePass123!",
        primary_subsidiary_id=sub_id
    )
    await UserService.create_user(db_session, user_in)
    
    # Try duplicate username
    dup_user = UserCreate(
        username="clara_smith",
        email="other@example.com",
        full_name="Clara Smith",
        password="SecurePass123!",
        primary_subsidiary_id=sub_id
    )
    with pytest.raises(ValueError, match="already in use"):
        await UserService.create_user(db_session, dup_user)

@pytest.mark.asyncio
async def test_create_user_weak_password(db_session: AsyncSession):
    sub_id = str(uuid.uuid4())
    user_in = UserCreate(
        username="weak_user",
        email="weak@example.com",
        full_name="Weak User",
        password="123",
        primary_subsidiary_id=sub_id
    )
    with pytest.raises(WeakPasswordError):
        await UserService.create_user(db_session, user_in)

@pytest.mark.asyncio
async def test_deactivate_self_fails(db_session: AsyncSession):
    sub_id = str(uuid.uuid4())
    user_in = UserCreate(
        username="self_deactivator",
        email="self@example.com",
        full_name="Self",
        password="SecurePass123!",
        primary_subsidiary_id=sub_id
    )
    user = await UserService.create_user(db_session, user_in)
    
    with pytest.raises(SelfDeactivationError):
        await UserService.update_user_status(db_session, user.id, is_active=False, actor_id=user.id)

@pytest.mark.asyncio
async def test_deactivate_last_admin_fails(db_session: AsyncSession):
    # Retrieve existing admin role (seeded automatically during setup_database)
    stmt = select(Role).where(Role.name == "admin")
    res = await db_session.execute(stmt)
    admin_role = res.scalars().first()
    if not admin_role:
        admin_role = Role(name="admin", permissions={})
        db_session.add(admin_role)
        await db_session.commit()
    
    admin_user = User(
        username="primary_admin",
        email="admin@example.com",
        hashed_password="hashed",
        is_active=True,
        is_superuser=True,
        role_id=admin_role.id
    )
    db_session.add(admin_user)
    await db_session.commit()
    
    # Deactivate all other active administrators in the database first to ensure this is the last one
    other_admins_stmt = select(User).where(
        User.id != admin_user.id,
        User.is_active == True,
        User.is_deleted == False,
        (User.is_superuser == True) | (User.role_id == admin_role.id)
    )
    other_admins = (await db_session.execute(other_admins_stmt)).scalars().all()
    for other in other_admins:
        other.is_active = False
        db_session.add(other)
    await db_session.commit()
    
    # Try to deactivate
    other_actor_id = uuid.uuid4()
    with pytest.raises(LastAdminDeactivationError):
        await UserService.update_user_status(db_session, admin_user.id, is_active=False, actor_id=other_actor_id)


@pytest.mark.asyncio
async def test_role_creation_and_uniqueness(db_session: AsyncSession):
    role_in = RoleCreate(
        name="sales_clerk",
        description="Handles sales transactions",
        permissions={"sales": {"sales_order": {"read": True}}}
    )
    role = await RoleService.create_role(db_session, role_in)
    assert role.name == "sales_clerk"
    
    # Try duplicate
    with pytest.raises(DuplicateRoleNameError):
        await RoleService.create_role(db_session, role_in)

@pytest.mark.asyncio
async def test_delete_assigned_role_fails(db_session: AsyncSession):
    role_in = RoleCreate(
        name="staff_role",
        permissions={}
    )
    role = await RoleService.create_role(db_session, role_in)
    
    user = User(
        username="assigned_user",
        email="assigned@example.com",
        hashed_password="hash",
        is_active=True,
        role_id=role.id
    )
    db_session.add(user)
    await db_session.commit()
    
    with pytest.raises(RoleAssignedToUsersError):
        await RoleService.delete_role(db_session, role.id)

@pytest.mark.asyncio
async def test_generate_and_revoke_api_key(db_session: AsyncSession):
    # 1. Provision a service account user
    sa_user = User(
        username="service_shopify",
        email="shopify@example.com",
        hashed_password="hash",
        is_active=True
    )
    db_session.add(sa_user)
    await db_session.commit()
    
    # 2. Generate key
    key_record, plaintext = await APIKeyService.generate_key(db_session, "Shopify Key", sa_user.id)
    assert plaintext.startswith("bes_live_")
    assert key_record.hashed_key is not None
    assert key_record.user_id == sa_user.id
    
    # 3. Revoke key
    await APIKeyService.revoke_key(db_session, key_record.id)
    db_key = await db_session.get(APIKey, key_record.id)
    assert db_key.is_active is False
    assert db_key.is_deleted is True
