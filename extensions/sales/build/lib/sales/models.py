import uuid
from sqlmodel import SQLModel, Field
from typing import Optional
from core.models import Customer, Product

class SalesCustomerDetails(SQLModel, table=True):
    __tablename__ = "sales_customer_details"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    customer_id: uuid.UUID = Field(foreign_key="customers.id", unique=True)
    
    credit_limit: float = Field(default=0.0)
    discount_tier: int = Field(default=1)

class SalesOrder(SQLModel, table=True):
    __tablename__ = "sales_orders"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    customer_id: uuid.UUID = Field(foreign_key="customers.id")
    total_amount: float = Field(default=0.0)
    status: str = Field(default="DRAFT")
