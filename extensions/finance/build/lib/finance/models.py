import uuid
from sqlmodel import SQLModel, Field
from core.models import Customer

class Invoice(SQLModel, table=True):
    __tablename__ = "finance_invoices"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    customer_id: uuid.UUID = Field(foreign_key="customers.id")
    amount: float = Field(default=0.0)
    is_paid: bool = Field(default=False)
