import uuid
from typing import Optional
from sqlmodel import SQLModel

class SupplyChainEntityCreate(SQLModel):
    name: str
    description: str = ""

class SupplyChainEntityRead(SQLModel):
    id: uuid.UUID
    name: str
    description: str
