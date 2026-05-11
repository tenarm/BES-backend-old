"""
Finance module business logic layer.
All complex operations (validation, balance updates, transaction safety)
live here — the router stays thin and only handles HTTP concerns.

Every mutation is audit-logged for process transparency.
"""
import logging
from decimal import Decimal
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

from .models import Account, JournalEntry, JournalEntryLine, JournalEntryStatus
from .schemas import AccountCreate, JournalEntryCreate
from core.audit import AuditService
from core.middleware import current_user_id_context, current_user_name_context

logger = logging.getLogger(__name__)


def _actor_info() -> tuple[str | None, str]:
    """Returns (actor_id, actor_name) from current request context."""
    return current_user_id_context.get(), current_user_name_context.get() or "system"


async def create_account(session: AsyncSession, data: AccountCreate) -> Account:
    """Creates a new account (Group or Ledger) in the hierarchy."""
    try:
        db_account = Account.model_validate(data)
        session.add(db_account)
        await session.flush()

        # Audit: record account creation
        actor_id, actor_name = _actor_info()
        await AuditService.log_action(
            session=session,
            entity_type="finance.Account",
            entity_id=db_account.id,
            action="CREATE",
            module="finance",
            description=f"Created account {data.code} — {data.name} ({data.type})",
            actor_id=actor_id,
            actor_name=actor_name,
            changes={"action_data": data.model_dump(mode="json")},
        )

        await session.commit()
        await session.refresh(db_account)
        return db_account
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Account code '{data.code}' already exists."
        )


async def create_journal_entry(session: AsyncSession, data: JournalEntryCreate) -> JournalEntry:
    """
    Creates a journal entry with lines and optionally updates account balances.
    All operations happen atomically — if any balance update fails, everything rolls back.
    Every mutation is audit-logged with field-level change tracking.
    """
    total_debit = sum(line.debit for line in data.lines)
    total_credit = sum(line.credit for line in data.lines)

    # 1. Validation — posted entries must balance
    if data.status == JournalEntryStatus.POSTED:
        if total_debit != total_credit:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot post unbalanced journal entry. "
                       f"Total Debit: {total_debit}, Total Credit: {total_credit}"
            )

    # 2. Create Header
    db_entry = JournalEntry(
        date=data.date,
        reference=data.reference,
        description=data.description,
        status=data.status
    )
    session.add(db_entry)
    await session.flush()

    # 3. Create Lines and Update Balances (if posted)
    balance_changes = []
    for line_data in data.lines:
        db_line = JournalEntryLine(
            journal_entry_id=db_entry.id,
            account_id=line_data.account_id,
            debit=line_data.debit,
            credit=line_data.credit,
            description=line_data.description
        )
        session.add(db_line)

        if data.status == JournalEntryStatus.POSTED:
            old_bal, new_bal = await _update_account_balance(
                session, line_data.account_id, line_data.debit, line_data.credit
            )
            balance_changes.append({
                "field": "balance",
                "old": str(old_bal),
                "new": str(new_bal),
                "context": f"Account {line_data.account_id}"
            })

    # 4. Audit: record journal entry creation
    actor_id, actor_name = _actor_info()
    await AuditService.log_action(
        session=session,
        entity_type="finance.JournalEntry",
        entity_id=db_entry.id,
        action="POST" if data.status == JournalEntryStatus.POSTED else "CREATE",
        module="finance",
        description=(
            f"{'Posted' if data.status == JournalEntryStatus.POSTED else 'Created draft'} "
            f"journal entry — {data.description} "
            f"(Debit: {total_debit}, Credit: {total_credit})"
        ),
        actor_id=actor_id,
        actor_name=actor_name,
        changes={
            "action_data": {
                "date": data.date,
                "reference": data.reference,
                "lines_count": len(data.lines),
                "total_debit": str(total_debit),
                "total_credit": str(total_credit),
            }
        },
        field_changes=balance_changes if balance_changes else None,
    )

    # 5. Commit atomically
    await session.commit()
    await session.refresh(db_entry)
    return db_entry


async def _update_account_balance(
    session: AsyncSession,
    account_id,
    debit: Decimal,
    credit: Decimal
) -> tuple[Decimal, Decimal]:
    """
    Updates an account's balance following standard accounting rules.
    Returns (old_balance, new_balance) for audit trail.
    """
    account_stmt = select(Account).where(Account.id == account_id)
    account_result = await session.execute(account_stmt)
    account = account_result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=400,
            detail=f"Account {account_id} not found for balance update"
        )

    old_balance = account.balance

    if account.type in ["Asset", "Expense"]:
        account.balance += (debit - credit)
    else:
        account.balance += (credit - debit)

    session.add(account)
    logger.debug(f"Updated balance for account {account.code}: {old_balance} → {account.balance}")
    return old_balance, account.balance
