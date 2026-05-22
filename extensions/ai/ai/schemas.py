import uuid
from typing import Optional
from sqlmodel import SQLModel

class AiEntityCreate(SQLModel):
    name: str
    description: str = ""

class AiEntityRead(SQLModel):
    id: uuid.UUID
    name: str
    description: str
