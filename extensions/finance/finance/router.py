from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from typing import List
from .models import Account, AccountCreate, AccountRead
from core.database import get_async_session
from core.responses import success_response

router = APIRouter(prefix="/api/v1/finance", tags=["finance"])

@router.get("/accounts")
async def get_accounts(session: AsyncSession = Depends(get_async_session)):
    """
    Returns a flattened list of all accounts for the Chart of Accounts.
    """
    stmt = select(Account).where(Account.is_deleted == False).order_by(Account.code)
    result = await session.execute(stmt)
    accounts = result.scalars().all()
    return success_response(data=accounts)

from sqlalchemy.exc import IntegrityError
from core.responses import success_response, error_response

@router.post("/accounts")
async def create_account(account_data: AccountCreate, session: AsyncSession = Depends(get_async_session)):
    """
    Creates a new account (Group or Ledger) in the hierarchy.
    Handles duplicate code errors gracefully.
    """
    try:
        db_account = Account.model_validate(account_data)
        session.add(db_account)
        await session.commit()
        await session.refresh(db_account)
        return success_response(data=db_account)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Account code '{account_data.code}' already exists."
        )

@router.get("/invoices")
def get_invoices():
    return {"status": "success", "data": []}
