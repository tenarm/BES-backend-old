from typing import Annotated, List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException
from core.responses import success_response
from core.database import get_session
from sqlmodel import Session, select
from .models import Quotation, QuotationItem, QuotationStatus, SalesOrder

router = APIRouter(prefix="/sales", tags=["sales"])

# --- Quotations ---

@router.get("/quotations")
def get_quotations(session: Annotated[Session, Depends(get_session)]):
    statement = select(Quotation).where(Quotation.is_deleted == False)
    results = session.exec(statement).all()
    return success_response(results)

@router.post("/quotations")
def create_quotation(
    quotation: Quotation, 
    items: List[QuotationItem],
    session: Annotated[Session, Depends(get_session)]
):
    session.add(quotation)
    session.flush()
    
    for item in items:
        item.quotation_id = quotation.id
        session.add(item)
    
    session.commit()
    session.refresh(quotation)
    return success_response(quotation)

@router.get("/quotations/{quotation_id}")
def get_quotation(
    quotation_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)]
):
    quotation = session.get(Quotation, quotation_id)
    if not quotation or quotation.is_deleted:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return success_response(quotation)

@router.post("/quotations/{quotation_id}/accept")
def accept_quotation(
    quotation_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)]
):
    quotation = session.get(Quotation, quotation_id)
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    
    quotation.status = QuotationStatus.ACCEPTED
    session.add(quotation)
    session.commit()
    return success_response(quotation)

# --- Sales Orders ---

@router.get("/orders")
def get_orders(session: Annotated[Session, Depends(get_session)]):
    statement = select(SalesOrder).where(SalesOrder.is_deleted == False)
    results = session.exec(statement).all()
    return success_response(results)

@router.post("/orders")
def create_order(
    order: SalesOrder,
    session: Annotated[Session, Depends(get_session)]
):
    session.add(order)
    session.commit()
    session.refresh(order)
    return success_response(order)

