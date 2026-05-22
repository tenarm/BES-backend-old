import uuid
from sqlmodel import Field
from core.models import BESBase

class SupplyChainEntity(BESBase, table=True):
    __tablename__ = "supply_chain_entities"
    
    name: str = Field(index=True)
    description: str = Field(default="")
