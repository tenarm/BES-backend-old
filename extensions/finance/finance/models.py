import uuid
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
from core.models import ERPBase
from decimal import Decimal
from enum import Enum

class AccountType(str, Enum):
    ASSET = "Asset"
    LIABILITY = "Liability"
    EQUITY = "Equity"
    INCOME = "Income"
    EXPENSE = "Expense"

# --- DB Models ---
class Account(ERPBase, table=True):
    __tablename__ = "finance_accounts"
    
    code: str = Field(index=True, unique=True)
    name: str
    type: AccountType
    is_group: bool = Field(default=False)
    parent_id: Optional[uuid.UUID] = Field(default=None, foreign_key="finance_accounts.id")
    balance: Decimal = Field(default=Decimal("0.0"), max_digits=20, decimal_places=4)

class Invoice(ERPBase, table=True):
    __tablename__ = "finance_invoices"
    customer_id: uuid.UUID = Field(foreign_key="customers.id")
    amount: Decimal = Field(default=Decimal("0.0"), max_digits=20, decimal_places=4)
    is_paid: bool = Field(default=False)

# --- API Schemas ---
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
