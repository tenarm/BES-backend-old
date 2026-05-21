import uuid
from typing import Optional
from sqlmodel import SQLModel

class SalesEntityCreate(SQLModel):
    name: str
    description: str = ""

class SalesEntityRead(SQLModel):
    id: uuid.UUID
    name: str
    description: str
