import uuid
from typing import Optional
from sqlmodel import SQLModel

class SettingsEntityCreate(SQLModel):
    name: str
    description: str = ""

class SettingsEntityRead(SQLModel):
    id: uuid.UUID
    name: str
    description: str
