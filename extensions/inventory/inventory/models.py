import uuid
from sqlmodel import Field
from core.models import BESBase

class InventoryEntity(BESBase, table=True):
    __tablename__ = "inventory_entities"
    
    name: str = Field(index=True)
    description: str = Field(default="")
