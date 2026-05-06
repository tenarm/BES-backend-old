from contextvars import ContextVar
from typing import Generator
from sqlmodel import Session, create_engine

# Context variable for multi-tenancy
subsidiary_id_context: ContextVar[str | None] = ContextVar("subsidiary_id_context", default=None)

# Simple sqlite for now to avoid postgres dependency during early dev
DATABASE_URL = "sqlite:///./erp.db"
engine = create_engine(DATABASE_URL, echo=True)

def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
