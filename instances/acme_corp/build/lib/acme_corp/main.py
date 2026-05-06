from fastapi import FastAPI
from contextlib import asynccontextmanager
from sqlmodel import SQLModel
from core.database import engine
from sales.router import router as sales_router
from finance.router import router as finance_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure all models are imported so SQLModel metadata gathers them
    from core import models as core_models
    from sales import models as sales_models
    from finance import models as finance_models
    
    # Create all tables (in real app, use Alembic migrations)
    SQLModel.metadata.create_all(engine)
    yield

app = FastAPI(title="Acme Corp ERP", lifespan=lifespan)

# Gather and register module routers
app.include_router(sales_router)
app.include_router(finance_router)

@app.get("/api/v1/bootstrap")
def bootstrap():
    from core.rbac import get_simplified_json
    return get_simplified_json("user_123")
