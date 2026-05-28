from fastapi import APIRouter, Depends
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user
from core.models import User, Customer, Product
from core.rbac import get_simplified_json
from core.database import get_async_session
from core.responses import success_response

from msme_basic.bootstrap import CLIENT_CONFIG, LICENSED_MODULES

router = APIRouter()

class CustomerCreate(BaseModel):
    name: str
    tax_id: Optional[str] = None
    primary_email: Optional[str] = None
    credit_limit: Decimal = Decimal("0.0")
    outstanding_balance: Decimal = Decimal("0.0")

class ProductCreate(BaseModel):
    name: str
    sku: str
    base_price: Decimal = Decimal("0.0")

@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "client": CLIENT_CONFIG.get("client_name"),
        "version": "0.1.0",
        "modules_loaded": len(LICENSED_MODULES),
    }

@router.get("/api/v1/bootstrap")
async def bootstrap(user: User = Depends(get_current_user)):
    """
    Returns the client configuration and the authenticated user's permissions,
    filtered to only the licensed modules for this client instance.
    """
    user_perms = get_simplified_json(user, licensed_modules=LICENSED_MODULES)

    return {
        "status": "success",
        "data": {
            "client_name": CLIENT_CONFIG.get("client_name"),
            "active_modules": LICENSED_MODULES,
            "plan": CLIENT_CONFIG.get("plan", "premium"),
            "user_id": str(user.id),
            "username": user.username,
            "permissions": user_perms["permissions"],
        }
    }

@router.post("/api/v1/customers")
async def create_customer(
    data: CustomerCreate,
    session: AsyncSession = Depends(get_async_session)
):
    customer = Customer(
        name=data.name,
        tax_id=data.tax_id,
        primary_email=data.primary_email,
        credit_limit=data.credit_limit,
        outstanding_balance=data.outstanding_balance
    )
    session.add(customer)
    await session.commit()
    await session.refresh(customer)
    return success_response(data=customer)

@router.get("/api/v1/customers")
async def list_customers(
    session: AsyncSession = Depends(get_async_session)
):
    stmt = select(Customer).where(Customer.is_deleted == False)
    result = await session.execute(stmt)
    customers = result.scalars().all()
    return success_response(data=customers)

@router.post("/api/v1/products")
async def create_product(
    data: ProductCreate,
    session: AsyncSession = Depends(get_async_session)
):
    product = Product(
        name=data.name,
        sku=data.sku,
        base_price=data.base_price
    )
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return success_response(data=product)

@router.get("/api/v1/products")
async def list_products(
    session: AsyncSession = Depends(get_async_session)
):
    stmt = select(Product).where(Product.is_deleted == False)
    result = await session.execute(stmt)
    products = result.scalars().all()
    return success_response(data=products)

