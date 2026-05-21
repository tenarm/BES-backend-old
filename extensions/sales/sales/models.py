import uuid
from sqlmodel import Field
from core.models import BESBase

class SalesEntity(BESBase, table=True):
    __tablename__ = "sales_entities"
    
    name: str = Field(index=True)
    description: str = Field(default="")
