import uuid
from typing import Optional
from sqlmodel import SQLModel

class InventoryEntityCreate(SQLModel):
    name: str
    description: str = ""

class InventoryEntityRead(SQLModel):
    id: uuid.UUID
    name: str
    description: str
