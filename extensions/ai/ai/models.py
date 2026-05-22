import uuid
from sqlmodel import Field
from core.models import BESBase

class AiEntity(BESBase, table=True):
    __tablename__ = "ai_entities"
    
    name: str = Field(index=True)
    description: str = Field(default="")
