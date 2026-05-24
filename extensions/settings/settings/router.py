import uuid
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core import get_current_user, User
from core.database import get_async_session
from core.responses import success_response, paginated_response
from core.pagination import PaginationParams
from core.licensing import require_licensed_feature
from core.rbac import require_permission

from .schemas import (
    CompanyProfileUpdate,
    CompanyProfileRead,
    SubsidiaryCreate,
    SubsidiaryUpdate,
    SubsidiaryRead,
    FiscalYearCreate,
    FiscalYearRead,
    PostingPeriodRead,
    TaxProfileCreate,
    TaxProfileRead,
    SharingRuleUpdate,
    SharingRuleRead,
    IntercompanyAccountCreate,
    IntercompanyAccountRead,
    UserInviteRequest,
    UserUpdatePayload,
    RoleCreate,
    RoleUpdate
)
from . import services

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

# --- Company Profile Endpoints ---
@router.get("/profile", response_model=None)
async def get_profile(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get the tenant-wide company profile details.
    Guarded by 'settings' + 'company_profile' license feature checks.
    """
    require_licensed_feature("settings", "company_profile")
    await require_permission("settings:profile:read")(current_user)
    
    profile = await services.get_or_create_profile(session)
    return success_response(data=profile)

@router.patch("/profile", response_model=None)
async def update_profile(
    data: CompanyProfileUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Update company profile configurations.
    Enforces optimistic locking control.
    """
    require_licensed_feature("settings", "company_profile")
    await require_permission("settings:profile:write")(current_user)
    
    profile = await services.update_profile(session, data, updater_name=current_user.username)
    return success_response(data=profile)


# --- Multi-Subsidiary Endpoints ---
@router.get("/subsidiaries", response_model=None)
async def get_subsidiaries(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """List all registered corporate subsidiary nodes."""
    require_licensed_feature("settings", "subsidiary_registry")
    await require_permission("settings:subsidiary:read")(current_user)
    
    items, total = await services.list_subsidiaries(session, pagination)
    return paginated_response(data=items, total=total, page=pagination.page, page_size=pagination.page_size)

@router.post("/subsidiaries", response_model=None)
async def create_subsidiary(
    data: SubsidiaryCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Register a new domestic or international subsidiary node."""
    require_licensed_feature("settings", "subsidiary_registry")
    await require_permission("settings:subsidiary:write")(current_user)
    
    item = await services.create_subsidiary(session, data)
    return success_response(data=item)

@router.patch("/subsidiaries/{id}", response_model=None)
async def update_subsidiary(
    id: uuid.UUID,
    data: SubsidiaryUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update subsidiary parameters under strict optimistic locking checks."""
    require_licensed_feature("settings", "subsidiary_registry")
    await require_permission("settings:subsidiary:write")(current_user)
    
    try:
        item = await services.update_subsidiary(session, id, data)
        return success_response(data=item)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.delete("/subsidiaries/{id}", response_model=None)
async def delete_subsidiary(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Soft-delete subsidiary organizational node."""
    require_licensed_feature("settings", "subsidiary_registry")
    await require_permission("settings:subsidiary:write")(current_user)
    
    try:
        await services.delete_subsidiary(session, id)
        return success_response(data={"message": "Subsidiary node successfully deleted"})
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# --- Fiscal Calendar Endpoints ---
@router.get("/fiscal-years", response_model=None)
async def get_fiscal_years(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """List operational corporate fiscal year calendars."""
    require_licensed_feature("settings", "fiscal_calendar")
    await require_permission("settings:fiscal:read")(current_user)
    
    items, total = await services.list_fiscal_years(session, pagination)
    return paginated_response(data=items, total=total, page=pagination.page, page_size=pagination.page_size)

@router.post("/fiscal-years", response_model=None)
async def create_fiscal_year(
    data: FiscalYearCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Setup fiscal year calendar bounds (Generates 12 posting sub-periods)."""
    require_licensed_feature("settings", "fiscal_calendar")
    await require_permission("settings:fiscal:write")(current_user)
    
    item = await services.create_fiscal_year(session, data)
    return success_response(data=item)

@router.get("/fiscal-years/{id}/periods", response_model=None)
async def get_posting_periods(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """List posting periods belonging to a specific fiscal year."""
    require_licensed_feature("settings", "fiscal_calendar")
    await require_permission("settings:fiscal:read")(current_user)
    
    items = await services.get_posting_periods(session, id)
    return success_response(data=items)

@router.post("/periods/{id}/lock", response_model=None)
async def lock_posting_period(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Lock an accounting posting period.
    Triggers DB pessimistic SELECT FOR UPDATE locks.
    """
    require_licensed_feature("settings", "fiscal_calendar")
    await require_permission("settings:fiscal:write")(current_user)
    
    try:
        item = await services.lock_posting_period(
            session=session,
            period_id=id,
            current_user_id=current_user.id,
            updater_name=current_user.username
        )
        return success_response(data=item)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# --- Tax regulatory setup Endpoints ---
@router.get("/tax-profiles", response_model=None)
async def get_tax_profiles(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """List regional tax authority profiles."""
    require_licensed_feature("settings", "tax_profile")
    await require_permission("settings:tax:read")(current_user)
    
    items, total = await services.list_tax_profiles(session, pagination)
    return paginated_response(data=items, total=total, page=pagination.page, page_size=pagination.page_size)

@router.post("/tax-profiles", response_model=None)
async def create_tax_profile(
    data: TaxProfileCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Associate a tax jurisdiction defaults rate with a subsidiary."""
    require_licensed_feature("settings", "tax_profile")
    await require_permission("settings:tax:write")(current_user)
    
    item = await services.create_tax_profile(session, data)
    return success_response(data=item)


# --- Data Sharing Rules Endpoints ---
@router.get("/sharing-rules", response_model=None)
async def get_sharing_rules(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """List customer/vendor/item master data sharing rules (Provisions default seeds)."""
    require_licensed_feature("settings", "data_sharing")
    await require_permission("settings:sharing:read")(current_user)
    
    rules = await services.get_or_seed_sharing_rules(session)
    return success_response(data=rules)

@router.put("/sharing-rules", response_model=None)
async def update_sharing_rules(
    rules: List[SharingRuleUpdate],
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Bulk update master sharing configurations."""
    require_licensed_feature("settings", "data_sharing")
    await require_permission("settings:sharing:write")(current_user)
    
    updated = await services.update_sharing_rules(session, rules)
    return success_response(data=updated)


# --- Intercompany G/L accounts Endpoints ---
@router.get("/intercompany-accounts", response_model=None)
async def get_intercompany_accounts(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """List mapped intercompany due-to/due-from GL accounts."""
    require_licensed_feature("settings", "data_sharing")
    await require_permission("settings:sharing:read")(current_user)
    
    items = await services.list_intercompany_accounts(session)
    return success_response(data=items)

@router.post("/intercompany-accounts", response_model=None)
async def create_intercompany_account(
    data: IntercompanyAccountCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Configure balancing intercompany accounts mappings."""
    require_licensed_feature("settings", "data_sharing")
    await require_permission("settings:sharing:write")(current_user)
    
    item = await services.create_intercompany_account(session, data)
    return success_response(data=item)


# --- User Directory & Invitation API Endpoints ---

@router.get("/users", response_model=None)
async def get_users(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    List all active workspace users.
    Guarded by 'settings' + 'user_management' licensing feature and settings:user:read permissions.
    """
    require_licensed_feature("settings", "user_management")
    await require_permission("settings:user:read")(current_user)

    items, total = await services.list_users(session, pagination)
    return paginated_response(
        data=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size
    )

@router.post("/users/invite", response_model=None)
async def create_user_invitation(
    data: UserInviteRequest,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new registration invitation token.
    Guarded by settings:user:write.
    """
    require_licensed_feature("settings", "user_management")
    await require_permission("settings:user:write")(current_user)

    try:
        invite = await services.invite_user(session, data, creator_name=current_user.username)
        return success_response(data=invite)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.patch("/users/{id}", response_model=None)
async def patch_user_details(
    id: uuid.UUID,
    data: UserUpdatePayload,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Updates user details (roles, allowed subsidiaries) with optimistic locking validation.
    Allowed subsidiaries updates requires 'settings' + 'subsidiary_scoping' licensing control.
    """
    require_licensed_feature("settings", "user_management")
    await require_permission("settings:user:write")(current_user)

    if data.allowed_subsidiary_ids is not None:
        require_licensed_feature("settings", "subsidiary_scoping")

    try:
        user = await services.update_user(session, id, data)
        return success_response(data=user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# --- Custom Role Endpoints ---

@router.get("/roles", response_model=None)
async def get_roles(
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """List custom RBAC roles."""
    require_licensed_feature("settings", "custom_rbac")
    await require_permission("settings:role:read")(current_user)

    roles = await services.list_roles(session)
    return success_response(data=roles)

@router.post("/roles", response_model=None)
async def create_custom_role(
    data: RoleCreate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Create custom rbac role."""
    require_licensed_feature("settings", "custom_rbac")
    await require_permission("settings:role:write")(current_user)

    role = await services.create_role(session, data)
    return success_response(data=role)

@router.patch("/roles/{id}", response_model=None)
async def patch_custom_role(
    id: uuid.UUID,
    data: RoleUpdate,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Update custom rbac role permissions accordions."""
    require_licensed_feature("settings", "custom_rbac")
    await require_permission("settings:role:write")(current_user)

    try:
        role = await services.update_role(session, id, data)
        return success_response(data=role)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# --- Active Session Revocation Endpoints ---

@router.get("/users/{id}/sessions", response_model=None)
async def get_user_sessions(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """List unrevoked active session tokens."""
    require_licensed_feature("settings", "session_revocation")
    await require_permission("settings:session:read")(current_user)

    sessions = await services.list_user_sessions(session, id)
    return success_response(data=sessions)

@router.delete("/sessions/{token_id}", response_model=None)
async def delete_active_session(
    token_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """Revokes active refresh token session using pessimistic locking."""
    require_licensed_feature("settings", "session_revocation")
    await require_permission("settings:session:write")(current_user)

    try:
        await services.revoke_session(session, token_id)
        return success_response(data={"message": "Active session token successfully revoked."})
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# --- User Offboarding Pipeline Endpoint ---

@router.put("/users/{id}/offboard", response_model=None)
async def trigger_user_offboarding(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Initiate User Deactivation and Session Revocation offboarding step.
    Locks user record via pessimistic locking to prevent concurrent authentication adjustments.
    """
    require_licensed_feature("settings", "user_management")
    await require_permission("settings:user:write")(current_user)

    try:
        res = await services.offboard_user(session, id, updater_name=current_user.username)
        return success_response(data=res)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

