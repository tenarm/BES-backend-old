import uuid
from typing import Optional
from decimal import Decimal
from sqlmodel import Field
from sqlalchemy import Column, Numeric
from core.models import BESBase


class FinanceRecord(BESBase, table=True):
    __tablename__ = "finance_records"
    
    name: str
    description: Optional[str] = None
    status: str = Field(default="DRAFT")
    amount: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(precision=20, scale=4))
    )
