from typing import Annotated, List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from core.responses import success_response
from core.database import get_async_session
from .models import Quotation, QuotationItem, QuotationStatus, SalesOrder

router = APIRouter(prefix="/api/v1/sales", tags=["sales"])

# --- Quotations ---

@router.get("/quotations")
async def get_quotations(session: AsyncSession = Depends(get_async_session)):
    statement = select(Quotation).where(Quotation.is_deleted == False)
    result = await session.execute(statement)
    results = result.scalars().all()
    return success_response(results)

@router.post("/quotations")
async def create_quotation(
    quotation: Quotation, 
    items: List[QuotationItem],
    session: AsyncSession = Depends(get_async_session)
):
    session.add(quotation)
    await session.flush()
    
    for item in items:
        item.quotation_id = quotation.id
        session.add(item)
    
    await session.commit()
    await session.refresh(quotation)
    return success_response(quotation)

@router.get("/quotations/{quotation_id}")
async def get_quotation(
    quotation_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session)
):
    quotation = await session.get(Quotation, quotation_id)
    if not quotation or quotation.is_deleted:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return success_response(quotation)

@router.post("/quotations/{quotation_id}/accept")
async def accept_quotation(
    quotation_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session)
):
    quotation = await session.get(Quotation, quotation_id)
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    
    quotation.status = QuotationStatus.ACCEPTED
    session.add(quotation)
    await session.commit()
    return success_response(quotation)

# --- Sales Orders ---

@router.get("/orders")
async def get_orders(session: AsyncSession = Depends(get_async_session)):
    statement = select(SalesOrder).where(SalesOrder.is_deleted == False)
    result = await session.execute(statement)
    results = result.scalars().all()
    return success_response(results)

@router.post("/orders")
async def create_order(
    order: SalesOrder,
    session: AsyncSession = Depends(get_async_session)
):
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return success_response(order)
