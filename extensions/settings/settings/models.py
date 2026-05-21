import uuid
from sqlmodel import Field
from core.models import BESBase

class SettingsEntity(BESBase, table=True):
    __tablename__ = "settings_entities"
    
    name: str = Field(index=True)
    description: str = Field(default="")
