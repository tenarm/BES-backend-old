import asyncio
from sqlmodel import SQLModel, create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from core.models import *
from finance.models import *
from sales.models import *
# Import other models as needed

DATABASE_URL = "sqlite:///acme_corp.db"

def sync_db():
    engine = create_engine(DATABASE_URL)
    print("Syncing database...")
    SQLModel.metadata.create_all(engine)
    print("Database synced successfully!")

if __name__ == "__main__":
    sync_db()
