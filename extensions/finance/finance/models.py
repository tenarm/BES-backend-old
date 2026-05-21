import uuid
from sqlmodel import Field
from core.models import BESBase

class FinanceEntity(BESBase, table=True):
    __tablename__ = "finance_entities"
    
    name: str = Field(index=True)
    description: str = Field(default="")
