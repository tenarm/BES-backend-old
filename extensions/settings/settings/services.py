import uuid
import logging
import calendar
import secrets
from datetime import date, datetime, timedelta
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError
from sqlmodel import select, func

from core.exceptions import ConcurrencyError
from core.pagination import PaginationParams

from .models import (
    SettingsEntity,
    CompanyProfile,
    Subsidiary,
    FiscalYear,
    PostingPeriod,
    TaxProfile,
    SharingRule,
    IntercompanyAccount,
    UserInvitation,
    UserSubsidiaryMapping
)
from .schemas import (
    SettingsEntityCreate,
    CompanyProfileCreate,
    CompanyProfileUpdate,
    SubsidiaryCreate,
    SubsidiaryUpdate,
    FiscalYearCreate,
    TaxProfileCreate,
    SharingRuleUpdate,
    IntercompanyAccountCreate,
    UserInviteRequest,
    UserUpdatePayload,
    RoleCreate,
    RoleUpdate
)
from .events import (
    emit_company_profile_updated,
    emit_subsidiary_created,
    emit_posting_period_locked,
    emit_user_invited,
    emit_user_role_changed,
    emit_user_session_revoked,
    emit_user_offboarded
)

logger = logging.getLogger(__name__)

# Legacy entity services
async def create_entity(session: AsyncSession, data: SettingsEntityCreate) -> SettingsEntity:
    db_obj = SettingsEntity.model_validate(data)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj

from core import Role, NotificationRule, User, RefreshToken

# --- Company Profile Service ---
async def get_or_create_profile(session: AsyncSession) -> CompanyProfile:
    """
    Get the tenant-wide company profile.
    If none exists, create a default profile record automatically.
    Also seeds default notification rules if missing.
    """
    stmt = select(CompanyProfile)
    result = await session.execute(stmt)
    profile = result.scalar_one_or_none()
    
    if not profile:
        logger.info("[Settings] No company profile found. Initializing default profile.")
        profile = CompanyProfile(
            name="Default Corporate Entity",
            legal_name="Default Corporate Entity Ltd",
            registration_id="000-000-000",
            timezone="UTC",
            base_currency="USD",
            date_format="YYYY-MM-DD",
            number_format="1,000.00"
        )
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
    
    # Auto-seed NotificationRule records
    role_stmt = select(Role).where(Role.name == "admin")
    role_result = await session.execute(role_stmt)
    admin_role = role_result.scalars().first()
    admin_role_id = str(admin_role.id) if admin_role else ""

    if admin_role_id:
        rules_stmt = select(NotificationRule)
        rules_result = await session.execute(rules_stmt)
        existing_rules = rules_result.scalars().all()
        
        if not existing_rules:
            logger.info("[Settings] Seeding default NotificationRule settings.")
            rule1 = NotificationRule(
                event_type="COMPANY_PROFILE_UPDATED",
                channel="EMAIL",
                recipient_type="ROLE",
                recipient_target=admin_role_id,
                template_title="[Security Alert] Company Profile Updated",
                template_body="The company profile details for tenant {{ tenant_name }} have been updated by user {{ updater_name }} on {{ timestamp }}. Please review the change logs."
            )
            rule2 = NotificationRule(
                event_type="POSTING_PERIOD_LOCKED",
                channel="IN_APP",
                recipient_type="ROLE",
                recipient_target=admin_role_id,
                template_title="Posting Period Closed: {{ period_name }}",
                template_body="Accounting posting period {{ period_name }} has been locked by {{ updater_name }} on {{ timestamp }}. Posting to this period is now disabled."
            )
            rule3 = NotificationRule(
                event_type="USER_INVITED",
                channel="EMAIL",
                recipient_type="DYNAMIC_PATH",
                recipient_target="$.data.target_email",
                template_title="Invitation to join {{ company_name }} on BES",
                template_body="Hello, you have been invited to join {{ company_name }} on the BES platform. Please click the link to complete your registration: {{ invitation_link }}"
            )
            rule4 = NotificationRule(
                event_type="USER_ROLE_CHANGED",
                channel="EMAIL",
                recipient_type="ROLE",
                recipient_target=admin_role_id,
                template_title="[Security Alert] User Role Modified",
                template_body="The role/permissions for user {{ target_user_email }} were updated by administrator {{ updater_name }} on {{ timestamp }}."
            )
            rule5 = NotificationRule(
                event_type="USER_SESSION_REVOKED",
                channel="IN_APP",
                recipient_type="ROLE",
                recipient_target=admin_role_id,
                template_title="[Security Notification] Active Session Revoked",
                template_body="Active session token ID {{ token_id }} for user ID {{ user_id }} has been terminated by administrator."
            )
            rule6 = NotificationRule(
                event_type="USER_OFFBOARDED",
                channel="EMAIL",
                recipient_type="ROLE",
                recipient_target=admin_role_id,
                template_title="[Deprovisioning Alert] User Offboarding Finalized",
                template_body="User account {{ username }} was deactivated and locked by admin {{ updater_name }} on {{ timestamp }}."
            )
            session.add(rule1)
            session.add(rule2)
            session.add(rule3)
            session.add(rule4)
            session.add(rule5)
            session.add(rule6)
            await session.commit()
            
    return profile

async def update_profile(session: AsyncSession, data: CompanyProfileUpdate, updater_name: str) -> CompanyProfile:
    """
    Update company profile details.
    Enforces optimistic locking version checks.
    """
    profile = await get_or_create_profile(session)
    
    # 1. Optimistic locking verification
    if profile.version_id != data.version_id:
        logger.warning(f"[Settings] Optimistic lock conflict on CompanyProfile. Payload: {data.version_id}, DB: {profile.version_id}")
        raise ConcurrencyError("The company profile was modified by another administrator. Please refresh.")

    # 2. Update fields
    update_dict = data.model_dump(exclude_unset=True, exclude={"version_id"})
    for key, value in update_dict.items():
        setattr(profile, key, value)
    
    session.add(profile)
    try:
        await session.commit()
        await session.refresh(profile)
    except StaleDataError:
        await session.rollback()
        raise ConcurrencyError("The company profile was modified concurrently by another user.")
    
    # 3. Emit update event
    await emit_company_profile_updated(updater_name=updater_name, tenant_name=profile.name)
    return profile


# --- Multi-Subsidiary Service ---
async def list_subsidiaries(session: AsyncSession, pagination: PaginationParams) -> tuple[List[Subsidiary], int]:
    """List all registered subsidiaries with pagination."""
    count_stmt = select(func.count()).select_from(Subsidiary).where(Subsidiary.is_deleted == False)
    total = (await session.execute(count_stmt)).scalar() or 0
    
    stmt = (
        select(Subsidiary)
        .where(Subsidiary.is_deleted == False)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total

async def create_subsidiary(session: AsyncSession, data: SubsidiaryCreate) -> Subsidiary:
    """Create and register a new subsidiary node in the MDM tree."""
    db_obj = Subsidiary.model_validate(data)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    
    # Emit provisioned event
    await emit_subsidiary_created(subsidiary_id=str(db_obj.id), name=db_obj.name)
    return db_obj

async def update_subsidiary(session: AsyncSession, id: uuid.UUID, data: SubsidiaryUpdate) -> Subsidiary:
    """Update subsidiary parameters with optimistic locking control."""
    stmt = select(Subsidiary).where(Subsidiary.id == id, Subsidiary.is_deleted == False)
    result = await session.execute(stmt)
    db_obj = result.scalar_one_or_none()
    
    if not db_obj:
        raise ValueError("Subsidiary not found")
        
    # Check stale writes
    if db_obj.version_id != data.version_id:
        raise ConcurrencyError("Stale subsidiary record detected. Please refresh.")
        
    update_dict = data.model_dump(exclude_unset=True, exclude={"version_id"})
    for key, value in update_dict.items():
        setattr(db_obj, key, value)
        
    session.add(db_obj)
    try:
        await session.commit()
        await session.refresh(db_obj)
    except StaleDataError:
        await session.rollback()
        raise ConcurrencyError("Subsidiary updated concurrently by another user.")
    return db_obj

async def delete_subsidiary(session: AsyncSession, id: uuid.UUID) -> None:
    """Soft-delete a subsidiary from the organizational tree."""
    stmt = select(Subsidiary).where(Subsidiary.id == id)
    result = await session.execute(stmt)
    db_obj = result.scalar_one_or_none()
    
    if not db_obj:
        raise ValueError("Subsidiary not found")
        
    db_obj.is_deleted = True
    session.add(db_obj)
    await session.commit()


# --- Fiscal Calendar Service ---
async def list_fiscal_years(session: AsyncSession, pagination: PaginationParams) -> tuple[List[FiscalYear], int]:
    count_stmt = select(func.count()).select_from(FiscalYear).where(FiscalYear.is_deleted == False)
    total = (await session.execute(count_stmt)).scalar() or 0
    
    stmt = (
        select(FiscalYear)
        .where(FiscalYear.is_deleted == False)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total

async def create_fiscal_year(session: AsyncSession, data: FiscalYearCreate) -> FiscalYear:
    """
    Setup a fiscal year calendar.
    Automatically generates 12 standard monthly posting periods.
    """
    # 1. Save fiscal calendar
    fy = FiscalYear.model_validate(data)
    session.add(fy)
    await session.commit()
    await session.refresh(fy)
    
    # 2. Generate 12 monthly sub-posting periods automatically
    start_dt = data.start_date
    current_year = start_dt.year
    current_month = start_dt.month
    
    for i in range(12):
        period_start = date(current_year, current_month, 1)
        last_day = calendar.monthrange(current_year, current_month)[1]
        period_end = date(current_year, current_month, last_day)
        
        month_name = calendar.month_name[current_month]
        period_name = f"{month_name} {current_year}"
        
        period = PostingPeriod(
            fiscal_year_id=fy.id,
            name=period_name,
            start_date=period_start,
            end_date=period_end,
            status="OPEN"
        )
        session.add(period)
        
        # Advance month calendar pointer
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1
            
    await session.commit()
    return fy

async def get_posting_periods(session: AsyncSession, fiscal_year_id: uuid.UUID) -> List[PostingPeriod]:
    """Get posting periods under a specific fiscal calendar."""
    stmt = select(PostingPeriod).where(PostingPeriod.fiscal_year_id == fiscal_year_id, PostingPeriod.is_deleted == False).order_by(PostingPeriod.start_date)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def lock_posting_period(session: AsyncSession, period_id: uuid.UUID, current_user_id: uuid.UUID, updater_name: str) -> PostingPeriod:
    """
    Seals ledger operations for a specific posting period.
    Employs SELECT FOR UPDATE pessimistic locking.
    """
    stmt = select(PostingPeriod).where(PostingPeriod.id == period_id).with_for_update()
    result = await session.execute(stmt)
    period = result.scalar_one_or_none()
    
    if not period:
        raise ValueError("Posting period not found")
        
    if period.status == "LOCKED":
        return period
        
    period.status = "LOCKED"
    period.locked_at = datetime.utcnow()
    period.locked_by = current_user_id
    
    session.add(period)
    await session.commit()
    await session.refresh(period)
    
    # Emit seal event
    await emit_posting_period_locked(period_id=str(period.id), period_name=period.name, updater_name=updater_name)
    return period


# --- Regional Tax Setup Service ---
async def list_tax_profiles(session: AsyncSession, pagination: PaginationParams) -> tuple[List[TaxProfile], int]:
    count_stmt = select(func.count()).select_from(TaxProfile).where(TaxProfile.is_deleted == False)
    total = (await session.execute(count_stmt)).scalar() or 0
    
    stmt = (
        select(TaxProfile)
        .where(TaxProfile.is_deleted == False)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    result = await session.execute(stmt)
    items = result.scalars().all()
    return items, total

async def create_tax_profile(session: AsyncSession, data: TaxProfileCreate) -> TaxProfile:
    """Associate a tax jurisdiction profile with a subsidiary."""
    tp = TaxProfile.model_validate(data)
    session.add(tp)
    await session.commit()
    await session.refresh(tp)
    return tp


# --- Data Sharing Rules Service ---
async def get_or_seed_sharing_rules(session: AsyncSession) -> List[SharingRule]:
    """Get active data sharing rules, seeding defaults if empty."""
    stmt = select(SharingRule).where(SharingRule.is_deleted == False)
    result = await session.execute(stmt)
    rules = list(result.scalars().all())
    
    if not rules:
        logger.info("[Settings] Seeding default cross-subsidiary master rules.")
        defaults = ["CUSTOMER", "VENDOR", "ITEM"]
        rules = []
        for entity in defaults:
            rule = SharingRule(entity_type=entity, is_globally_shared=True)
            session.add(rule)
            rules.append(rule)
        await session.commit()
        for r in rules:
            await session.refresh(r)
            
    return rules

async def update_sharing_rules(session: AsyncSession, rules_data: List[SharingRuleUpdate]) -> List[SharingRule]:
    """Bulk update master sharing rules (Optimistic locking validation)."""
    updated_rules = []
    for data in rules_data:
        stmt = select(SharingRule).where(SharingRule.entity_type == data.entity_type, SharingRule.is_deleted == False)
        result = await session.execute(stmt)
        rule = result.scalar_one_or_none()
        
        if not rule:
            continue
            
        if rule.version_id != data.version_id:
            raise ConcurrencyError(f"Stale rules registry detected on '{data.entity_type}'. Please refresh.")
            
        rule.is_globally_shared = data.is_globally_shared
        session.add(rule)
        updated_rules.append(rule)
        
    try:
        await session.commit()
        for r in updated_rules:
            await session.refresh(r)
    except StaleDataError:
        await session.rollback()
        raise ConcurrencyError("Concurrency rules adjustment write conflict.")
        
    return updated_rules


# --- Intercompany Accounts Mapping Service ---
async def list_intercompany_accounts(session: AsyncSession) -> List[IntercompanyAccount]:
    stmt = select(IntercompanyAccount).where(IntercompanyAccount.is_deleted == False)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def create_intercompany_account(session: AsyncSession, data: IntercompanyAccountCreate) -> IntercompanyAccount:
    """Setup dual intercompany balancing accounts mapping."""
    ica = IntercompanyAccount.model_validate(data)
    session.add(ica)
    await session.commit()
    await session.refresh(ica)
    return ica


# --- User Directory & Invitation Services ---

async def list_users(session: AsyncSession, pagination: PaginationParams) -> tuple[List[dict], int]:
    """List all registered users with their allowed subsidiary IDs and roles, support pagination."""
    count_stmt = select(func.count()).select_from(User).where(User.is_deleted == False)
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = (
        select(User)
        .where(User.is_deleted == False)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    result = await session.execute(stmt)
    users = result.scalars().all()

    mapped_users = []
    for u in users:
        # Load allowed subsidiary mappings
        sub_stmt = select(UserSubsidiaryMapping.allowed_subsidiary_id).where(
            UserSubsidiaryMapping.user_id == u.id,
            UserSubsidiaryMapping.is_deleted == False
        )
        sub_res = await session.execute(sub_stmt)
        allowed_subs = list(sub_res.scalars().all())

        mapped_users.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "full_name": u.full_name,
            "is_active": u.is_active,
            "role_id": u.role_id,
            "allowed_subsidiary_ids": allowed_subs,
            "version_id": u.version_id
        })

    return mapped_users, total

async def invite_user(session: AsyncSession, data: UserInviteRequest, creator_name: str) -> UserInvitation:
    """Creates a secure onboarding token and triggers a USER_INVITED pub/sub event."""
    # Check duplicate email
    user_stmt = select(User).where(User.email == data.email, User.is_deleted == False)
    existing_user = (await session.execute(user_stmt)).scalar_one_or_none()
    if existing_user:
        raise ValueError("User with this email is already registered.")

    invite_stmt = select(UserInvitation).where(
        UserInvitation.email == data.email,
        UserInvitation.status == "PENDING",
        UserInvitation.is_deleted == False
    )
    existing_invite = (await session.execute(invite_stmt)).scalar_one_or_none()
    if existing_invite:
        # Invalidate previous invite
        existing_invite.status = "EXPIRED"
        session.add(existing_invite)

    # Secure registration token
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=24)

    invitation = UserInvitation(
        email=data.email,
        role_id=data.role_id,
        token=token,
        expires_at=expires_at,
        status="PENDING"
    )
    invitation.created_by = creator_name
    session.add(invitation)
    await session.commit()
    await session.refresh(invitation)

    # Emit invitation event
    await emit_user_invited(email=invitation.email, token=invitation.token)
    return invitation

async def update_user(session: AsyncSession, user_id: uuid.UUID, data: UserUpdatePayload) -> dict:
    """Updates user active status, full name, roles, and subsidiary mappings under optimistic locking."""
    stmt = select(User).where(User.id == user_id, User.is_deleted == False)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("User not found")

    # Optimistic locking check
    if user.version_id != data.version_id:
        raise ConcurrencyError("The user details were modified by another administrator. Please refresh.")

    if data.full_name is not None:
        user.full_name = data.full_name
    if data.role_id is not None:
        user.role_id = data.role_id
    if data.is_active is not None:
        user.is_active = data.is_active

    session.add(user)

    if data.allowed_subsidiary_ids is not None:
        # Soft-delete previous subsidiary scopes
        mappings_stmt = select(UserSubsidiaryMapping).where(
            UserSubsidiaryMapping.user_id == user_id,
            UserSubsidiaryMapping.is_deleted == False
        )
        mappings_res = await session.execute(mappings_stmt)
        old_mappings = mappings_res.scalars().all()
        for mapping in old_mappings:
            mapping.is_deleted = True
            session.add(mapping)

        # Bulk insert new mappings
        for sub_id in data.allowed_subsidiary_ids:
            new_mapping = UserSubsidiaryMapping(
                user_id=user_id,
                allowed_subsidiary_id=sub_id
            )
            session.add(new_mapping)

    try:
        await session.commit()
        await session.refresh(user)
    except StaleDataError:
        await session.rollback()
        raise ConcurrencyError("User updated concurrently by another admin.")

    # Fetch updated subsidiary mappings
    sub_stmt = select(UserSubsidiaryMapping.allowed_subsidiary_id).where(
        UserSubsidiaryMapping.user_id == user.id,
        UserSubsidiaryMapping.is_deleted == False
    )
    sub_res = await session.execute(sub_stmt)
    allowed_subs = list(sub_res.scalars().all())

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "role_id": user.role_id,
        "allowed_subsidiary_ids": allowed_subs,
        "version_id": user.version_id
    }


# --- Custom Role Services ---

async def list_roles(session: AsyncSession) -> List[Role]:
    """List all registered system roles."""
    stmt = select(Role).where(Role.is_deleted == False)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def create_role(session: AsyncSession, data: RoleCreate) -> Role:
    """Registers a new custom role with a specific permissions structure."""
    role = Role(
        name=data.name,
        description=data.description,
        sa_column_kwargs={"permissions": data.permissions}
    )
    role.permissions = data.permissions
    session.add(role)
    await session.commit()
    await session.refresh(role)
    return role

async def update_role(session: AsyncSession, role_id: uuid.UUID, data: RoleUpdate) -> Role:
    """Updates custom role permissions accordion map."""
    stmt = select(Role).where(Role.id == role_id, Role.is_deleted == False)
    result = await session.execute(stmt)
    role = result.scalar_one_or_none()
    if not role:
        raise ValueError("Role not found")

    # Optimistic locking check
    if role.version_id != data.version_id:
        raise ConcurrencyError("Role was modified by another user. Please refresh.")

    if data.description is not None:
        role.description = data.description
    if data.permissions is not None:
        role.permissions = data.permissions

    session.add(role)
    try:
        await session.commit()
        await session.refresh(role)
    except StaleDataError:
        await session.rollback()
        raise ConcurrencyError("Role modified concurrently.")

    await emit_user_role_changed(role_id=str(role.id), role_name=role.name)
    return role


# --- Active Session Revocation Services ---

async def list_user_sessions(session: AsyncSession, user_id: uuid.UUID) -> List[RefreshToken]:
    """Retrieves all active unrevoked refresh tokens (sessions) for a user."""
    stmt = select(RefreshToken).where(
        RefreshToken.user_id == user_id,
        RefreshToken.is_revoked == False,
        RefreshToken.expires_at > datetime.utcnow()
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def revoke_session(session: AsyncSession, token_id: uuid.UUID) -> RefreshToken:
    """Revokes a refresh token session using pessimistic locking."""
    stmt = select(RefreshToken).where(RefreshToken.id == token_id).with_for_update()
    result = await session.execute(stmt)
    token = result.scalar_one_or_none()
    if not token:
        raise ValueError("Active session token not found")

    if not token.is_revoked:
        token.is_revoked = True
        session.add(token)
        await session.commit()
        await session.refresh(token)

    await emit_user_session_revoked(token_id=str(token.id), user_id=str(token.user_id))
    return token


# --- User Offboarding Deprovisioning Services ---

async def offboard_user(session: AsyncSession, user_id: uuid.UUID, updater_name: str) -> dict:
    """
    Triggers User Deactivation and Session Revocation under Pessimistic locking.
    Prepares account for the final offboarding lockout step.
    """
    stmt = select(User).where(User.id == user_id).with_for_update()
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("User not found")

    # 1. Deactivate account
    user.is_active = False
    session.add(user)

    # 2. Revoke all active session tokens
    session_stmt = select(RefreshToken).where(
        RefreshToken.user_id == user_id,
        RefreshToken.is_revoked == False
    )
    session_res = await session.execute(session_stmt)
    active_tokens = session_res.scalars().all()
    for token in active_tokens:
        token.is_revoked = True
        session.add(token)

    await session.commit()
    await session.refresh(user)

    # Emit offboarded event
    await emit_user_offboarded(user_id=str(user.id), username=user.username, updater_name=updater_name)

    return {
        "id": user.id,
        "username": user.username,
        "is_active": user.is_active,
        "status": "OFFBOARDED"
    }

