"""
Finance API Router.
Thin HTTP layer — delegates all business logic to services.py.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from .models import Account, JournalEntry, JournalEntryLine, JournalEntryStatus
from .schemas import AccountCreate, JournalEntryCreate, JournalEntryRead, JournalEntryLineRead
from .services import create_account, create_journal_entry
from core.database import get_async_session
from core.responses import success_response, paginated_response
from core.pagination import PaginationParams

router = APIRouter(prefix="/api/v1/finance", tags=["finance"])


# --- Accounts (Chart of Accounts) ---

@router.get("/accounts")
async def get_accounts(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    """Returns a paginated list of all accounts for the Chart of Accounts."""
    # Count total
    count_stmt = select(func.count()).select_from(Account).where(Account.is_deleted == False)
    total = (await session.execute(count_stmt)).scalar() or 0

    # Fetch page
    stmt = (
        select(Account)
        .where(Account.is_deleted == False)
        .order_by(Account.code)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    result = await session.execute(stmt)
    accounts = result.scalars().all()

    return paginated_response(
        data=accounts,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size
    )


@router.post("/accounts")
async def create_account_endpoint(
    account_data: AccountCreate,
    session: AsyncSession = Depends(get_async_session)
):
    """Creates a new account (Group or Ledger) in the hierarchy."""
    db_account = await create_account(session, account_data)
    return success_response(data=db_account)


# --- Journal Entries ---

@router.get("/journal-entries")
async def get_journal_entries(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    """Returns a paginated list of journal entry headers."""
    count_stmt = select(func.count()).select_from(JournalEntry).where(JournalEntry.is_deleted == False)
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = (
        select(JournalEntry)
        .where(JournalEntry.is_deleted == False)
        .order_by(JournalEntry.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    result = await session.execute(stmt)
    entries = result.scalars().all()

    return paginated_response(
        data=entries,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size
    )


@router.get("/journal-entries/{entry_id}")
async def get_journal_entry_detail(
    entry_id: str,
    session: AsyncSession = Depends(get_async_session)
):
    """Returns a journal entry with its lines."""
    entry_stmt = select(JournalEntry).where(JournalEntry.id == entry_id, JournalEntry.is_deleted == False)
    entry_result = await session.execute(entry_stmt)
    entry = entry_result.scalars().first()

    if not entry:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Journal entry not found")

    lines_stmt = select(JournalEntryLine).where(JournalEntryLine.journal_entry_id == entry_id)
    lines_result = await session.execute(lines_stmt)
    lines = lines_result.scalars().all()

    return success_response(data={
        "entry": entry,
        "lines": lines
    })


@router.post("/journal-entries")
async def create_journal_entry_endpoint(
    entry_data: JournalEntryCreate,
    session: AsyncSession = Depends(get_async_session)
):
    """Creates a journal entry with lines. Posts and updates balances if status is Posted."""
    db_entry = await create_journal_entry(session, entry_data)
    return success_response(data=db_entry)


# --- Invoices (stub) ---

@router.get("/invoices")
async def get_invoices():
    return success_response(data=[])
