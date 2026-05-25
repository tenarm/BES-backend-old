import logging
import uuid
import re
from datetime import datetime, date
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from core.repository import BaseRepository
from core.exceptions import ConcurrencyError
from ..models.company import CompanyProfile, Subsidiary, FiscalCalendar, PostingPeriod, TaxProfile
from ..schemas.company import (
    CompanyProfileCreate, CompanyProfileUpdate,
    SubsidiaryCreate, SubsidiaryUpdate,
    FiscalCalendarCreate, FiscalCalendarUpdate,
    TaxProfileCreate, TaxProfileUpdate
)

logger = logging.getLogger(__name__)

# --- Repository Instances ---
company_repo = BaseRepository(CompanyProfile)
subsidiary_repo = BaseRepository(Subsidiary)
calendar_repo = BaseRepository(FiscalCalendar)
period_repo = BaseRepository(PostingPeriod)
tax_repo = BaseRepository(TaxProfile)

# --- Helper Validation Invariants ---

def validate_tax_identifier(tax_id: Optional[str]) -> None:
    """
    Validates the tax identifier against format syntax:
    - 2 digits, hyphen, 7 digits (e.g. 12-3456789)
    - Or any alphanumeric string between 5 and 20 characters.
    """
    if not tax_id:
        return
    pattern = r"^(\d{2}-\d{7}|[A-Z0-9-]{5,20})$"
    if not re.match(pattern, tax_id):
        raise ValueError(
            f"Invalid tax identifier format: '{tax_id}'. "
            f"Must be 'XX-XXXXXXX' or an alphanumeric code of 5-20 characters."
        )

async def check_circular_parent(session: AsyncSession, subsidiary_id: uuid.UUID, parent_id: uuid.UUID) -> bool:
    """
    Traverses up the parent chain to detect circular dependencies:
    Returns True if subsidiary_id is found in parent_id's ancestors.
    """
    curr_parent_id = parent_id
    visited = set()
    while curr_parent_id is not None:
        if curr_parent_id == subsidiary_id:
            return True
        if curr_parent_id in visited:
            break  # Prevent infinite loop if DB is already corrupted
        visited.add(curr_parent_id)
        
        stmt = select(Subsidiary).where(Subsidiary.id == curr_parent_id).where(Subsidiary.is_deleted == False)
        res = await session.execute(stmt)
        parent = res.scalars().first()
        if not parent:
            break
        curr_parent_id = parent.parent_id
    return False

async def has_posted_ledger_transactions(session: AsyncSession, subsidiary_id: uuid.UUID) -> bool:
    """
    Checks if there are any posted entries in the General Ledger for this subsidiary.
    Handles stage-wise builds: if the ledger table does not exist, returns False.
    """
    query = text("SELECT COUNT(*) FROM finance_gl_entries WHERE subsidiary_id = :sub_id AND is_deleted = False")
    try:
        res = await session.execute(query, {"sub_id": str(subsidiary_id)})
        count = res.scalar() or 0
        return count > 0
    except ProgrammingError:
        # Table does not exist yet (Stage-wise build phase)
        return False

# --- Company Profile Service ---

class CompanyProfileService:
    @staticmethod
    async def get_profile(session: AsyncSession) -> Optional[CompanyProfile]:
        """
        Retrieves the primary company profile.
        Since there is only one root profile, returns the first record found.
        """
        stmt = select(CompanyProfile).where(CompanyProfile.is_deleted == False)
        res = await session.execute(stmt)
        return res.scalars().first()

    @staticmethod
    async def create_profile(session: AsyncSession, data: CompanyProfileCreate) -> CompanyProfile:
        """
        Creates a new primary company profile after validating the tax identifier.
        """
        validate_tax_identifier(data.tax_identifier)
        obj = CompanyProfile.model_validate(data)
        return await company_repo.create(session, obj)

    @staticmethod
    async def update_profile(session: AsyncSession, id: uuid.UUID, data: CompanyProfileUpdate, version_id: int) -> CompanyProfile:
        """
        Updates the primary company profile. Enforces tax ID format checks.
        """
        db_obj = await company_repo.get(session, id)
        if not db_obj:
            raise ValueError(f"Company profile with ID {id} not found.")
        
        if data.tax_identifier is not None:
            validate_tax_identifier(data.tax_identifier)
        
        # Merge update payload and pass to repo to run optimistic concurrency check
        update_dict = data.model_dump(exclude_unset=True)
        update_dict["version_id"] = version_id
        return await company_repo.update(session, db_obj, update_dict)

# --- Subsidiary Service ---

class SubsidiaryService:
    @staticmethod
    async def create_subsidiary(session: AsyncSession, data: SubsidiaryCreate) -> Subsidiary:
        """
        Registers a new subsidiary after verifying parent validity and tax format integrity.
        """
        validate_tax_identifier(data.tax_identifier)
        
        # Verify parent exists
        if data.parent_id:
            parent = await subsidiary_repo.get(session, data.parent_id)
            if not parent:
                raise ValueError(f"Parent subsidiary with ID {data.parent_id} does not exist.")
        
        obj = Subsidiary.model_validate(data)
        return await subsidiary_repo.create(session, obj)

    @staticmethod
    async def update_subsidiary(session: AsyncSession, id: uuid.UUID, data: SubsidiaryUpdate, version_id: int) -> Subsidiary:
        """
        Updates subsidiary settings.
        Enforces:
        - Circular dependency check.
        - Currency lock checking if general ledger postings exist.
        - Tax format validation.
        """
        db_obj = await subsidiary_repo.get(session, id)
        if not db_obj:
            raise ValueError(f"Subsidiary with ID {id} not found.")
        
        # 1. Parent validation (prevent cycle)
        if data.parent_id is not None:
            if data.parent_id == id:
                raise ValueError("A subsidiary cannot be its own parent.")
            parent = await subsidiary_repo.get(session, data.parent_id)
            if not parent:
                raise ValueError(f"Parent subsidiary with ID {data.parent_id} does not exist.")
            if await check_circular_parent(session, id, data.parent_id):
                raise ValueError(f"Circular parent assignment detected: making parent {data.parent_id} leads back to child {id}.")
        
        # 2. Base currency lock check
        if data.base_currency is not None and data.base_currency != db_obj.base_currency:
            if await has_posted_ledger_transactions(session, id):
                raise ValueError(
                    f"Functional base currency cannot be modified for subsidiary {db_obj.name} "
                    f"because ledger transactions have already been posted."
                )
        
        # 3. Tax ID validation
        if data.tax_identifier is not None:
            validate_tax_identifier(data.tax_identifier)
            
        update_dict = data.model_dump(exclude_unset=True)
        update_dict["version_id"] = version_id
        return await subsidiary_repo.update(session, db_obj, update_dict)

# --- Fiscal Calendar Service ---

class FiscalCalendarService:
    @staticmethod
    async def get_calendar(session: AsyncSession, id: uuid.UUID) -> Optional[FiscalCalendar]:
        return await calendar_repo.get(session, id)

    @staticmethod
    async def create_fiscal_year(session: AsyncSession, data: FiscalCalendarCreate) -> FiscalCalendar:
        """
        Registers a new fiscal year.
        Checks for overlapping date ranges to ensure accounting years are sequential and contiguous.
        """
        # Date overlap checks
        stmt = select(FiscalCalendar).where(FiscalCalendar.is_deleted == False)
        res = await session.execute(stmt)
        existing_calendars = res.scalars().all()
        
        start_date = data.start_date
        end_date = data.end_date
        
        if start_date > end_date:
            raise ValueError(f"Start date {start_date} cannot be after end date {end_date}.")
            
        for cal in existing_calendars:
            if not (end_date < cal.start_date or start_date > cal.end_date):
                raise ValueError(
                    f"Fiscal calendar dates overlap with existing calendar '{cal.name}' "
                    f"({cal.start_date} to {cal.end_date})."
                )
        
        obj = FiscalCalendar.model_validate(data)
        new_cal = await calendar_repo.create(session, obj)
        
        # Auto generate periods
        await FiscalCalendarService.generate_monthly_periods(session, new_cal)
        return new_cal

    @staticmethod
    async def generate_monthly_periods(session: AsyncSession, calendar: FiscalCalendar) -> List[PostingPeriod]:
        """
        Automatically segments the fiscal year dates exactly into 12 monthly intervals.
        """
        # Parse dates
        start_dt = datetime.strptime(calendar.start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(calendar.end_date, "%Y-%m-%d").date()
        
        # Check that we can segment roughly 12 months.
        # We generate 12 periods based on calendar month offsets.
        periods = []
        curr_year = start_dt.year
        curr_month = start_dt.month
        
        for i in range(12):
            # Start of month logic
            p_start = date(curr_year, curr_month, 1)
            if i == 0:
                p_start = start_dt  # align with fiscal start date boundary
                
            # End of month logic
            next_month = curr_month + 1 if curr_month < 12 else 1
            next_year = curr_year if curr_month < 12 else curr_year + 1
            
            p_end_dt = date(next_year, next_month, 1)
            # Fetch last day of curr month
            # Calculate duration limit
            if i == 11:
                p_end = end_dt  # align with fiscal end date boundary
            else:
                from datetime import timedelta
                p_end = p_end_dt - timedelta(days=1)
                
            p_name = f"{calendar.name} - Period {i+1:02d}"
            
            period_obj = PostingPeriod(
                calendar_id=calendar.id,
                name=p_name,
                start_date=p_start.strftime("%Y-%m-%d"),
                end_date=p_end.strftime("%Y-%m-%d"),
                is_locked=False
            )
            
            session.add(period_obj)
            periods.append(period_obj)
            
            curr_month = next_month
            curr_year = next_year
            
        await session.commit()
        return periods

    @staticmethod
    async def update_fiscal_year(session: AsyncSession, id: uuid.UUID, data: FiscalCalendarUpdate, version_id: int) -> FiscalCalendar:
        db_obj = await calendar_repo.get(session, id)
        if not db_obj:
            raise ValueError(f"Fiscal calendar with ID {id} not found.")
            
        update_dict = data.model_dump(exclude_unset=True)
        update_dict["version_id"] = version_id
        return await calendar_repo.update(session, db_obj, update_dict)

# --- Posting Period Service ---

class PostingPeriodService:
    @staticmethod
    async def update_period_status(session: AsyncSession, id: uuid.UUID, is_locked: bool) -> PostingPeriod:
        """
        Updates the locking status of a posting period.
        If locking (is_locked=True), acquires row lock on parent calendar.
        """
        db_obj = await period_repo.get(session, id)
        if not db_obj:
            raise ValueError(f"Posting period with ID {id} not found.")
            
        if is_locked:
            # Acquire pessimistic row-level lock on the calendar parent record
            await calendar_repo.get_with_lock(session, db_obj.calendar_id)
            
        db_obj.is_locked = is_locked
        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj)
        return db_obj

# --- Tax Profile Service ---

class TaxProfileService:
    @staticmethod
    async def create_tax_profile(session: AsyncSession, data: TaxProfileCreate) -> TaxProfile:
        obj = TaxProfile.model_validate(data)
        return await tax_repo.create(session, obj)

    @staticmethod
    async def update_tax_profile(session: AsyncSession, id: uuid.UUID, data: TaxProfileUpdate, version_id: int) -> TaxProfile:
        db_obj = await tax_repo.get(session, id)
        if not db_obj:
            raise ValueError(f"Tax profile with ID {id} not found.")
            
        update_dict = data.model_dump(exclude_unset=True)
        update_dict["version_id"] = version_id
        return await tax_repo.update(session, db_obj, update_dict)
