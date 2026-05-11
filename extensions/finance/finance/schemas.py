"""
Finance module API schemas.
Separated from models.py to enforce the boundary between
ORM/table definitions and API request/response contracts.
"""
import uuid
from typing import Optional, List
from decimal import Decimal
from sqlmodel import SQLModel
from .models import AccountType, JournalEntryStatus


# --- Account Schemas ---
class AccountBase(SQLModel):
    code: str
    name: str
    type: AccountType
    is_group: bool = False
    parent_id: Optional[uuid.UUID] = None

class AccountCreate(AccountBase):
    pass

class AccountRead(AccountBase):
    id: uuid.UUID
    balance: Decimal


# --- Journal Entry Schemas ---
class JournalEntryLineBase(SQLModel):
    account_id: uuid.UUID
    debit: Decimal = Decimal("0.0")
    credit: Decimal = Decimal("0.0")
    description: Optional[str] = None

class JournalEntryLineCreate(JournalEntryLineBase):
    pass

class JournalEntryLineRead(JournalEntryLineBase):
    id: uuid.UUID

class JournalEntryBase(SQLModel):
    date: str
    reference: Optional[str] = None
    description: str
    status: JournalEntryStatus = JournalEntryStatus.DRAFT

class JournalEntryCreate(JournalEntryBase):
    lines: List[JournalEntryLineCreate]

class JournalEntryRead(JournalEntryBase):
    id: uuid.UUID
    lines: List[JournalEntryLineRead] = []
