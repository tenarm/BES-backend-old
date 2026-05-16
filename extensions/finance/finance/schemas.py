import uuid
from decimal import Decimal
from typing import Optional
from sqlmodel import SQLModel


class FinanceRecordCreate(SQLModel):
    name: str
    description: Optional[str] = None
    amount: Decimal = Decimal("0.0")


class FinanceRecordRead(SQLModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    status: str
    amount: Decimal
