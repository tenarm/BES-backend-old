import uuid
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from core.models import BESBase
from decimal import Decimal
from enum import Enum
from sqlalchemy import Column, Numeric


class AccountType(str, Enum):
    ASSET = "Asset"
    LIABILITY = "Liability"
    EQUITY = "Equity"
    INCOME = "Income"
    EXPENSE = "Expense"


class JournalEntryStatus(str, Enum):
    DRAFT = "Draft"
    POSTED = "Posted"


# --- DB Table Models (no API schemas here) ---

class Account(BESBase, table=True):
    __tablename__ = "finance_accounts"

    code: str = Field(index=True, unique=True)
    name: str
    type: AccountType
    is_group: bool = Field(default=False)
    parent_id: Optional[uuid.UUID] = Field(default=None, foreign_key="finance_accounts.id")
    balance: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )


class Invoice(BESBase, table=True):
    __tablename__ = "finance_invoices"
    customer_id: uuid.UUID = Field(foreign_key="customers.id")
    amount: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    is_paid: bool = Field(default=False)


class JournalEntry(BESBase, table=True):
    __tablename__ = "finance_journal_entries"

    date: str  # ISO Date string YYYY-MM-DD
    reference: Optional[str] = None
    description: str
    status: JournalEntryStatus = Field(default=JournalEntryStatus.DRAFT)


class JournalEntryLine(BESBase, table=True):
    __tablename__ = "finance_journal_entry_lines"

    journal_entry_id: uuid.UUID = Field(foreign_key="finance_journal_entries.id")
    account_id: uuid.UUID = Field(foreign_key="finance_accounts.id")
    debit: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    credit: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
    description: Optional[str] = None
