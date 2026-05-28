import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from core.database import get_async_session
from core.responses import success_response, paginated_response
from core.pagination import PaginationParams
from core.licensing import require_licensed_feature
from core.rbac import require_permission
from core.exceptions import ValidationError, EntityNotFoundError, StateTransitionError

from .schemas import FinanceInvoiceCreate, FinancePaymentCreate
from .services import InvoiceService, PaymentService
from .models import FinanceInvoice, FinancePayment

router = APIRouter(prefix="/api/v1/finance", tags=["Finance"])
invoice_service = InvoiceService()
payment_service = PaymentService()


# --- Invoice Endpoints ---

@router.post("/invoices", dependencies=[Depends(require_permission("finance:invoices:write"))])
async def create_invoice(
    data: FinanceInvoiceCreate,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("finance", "invoices")
    try:
        invoice = await invoice_service.create_invoice(session, data)
        return success_response(data=invoice)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)


@router.get("/invoices", dependencies=[Depends(require_permission("finance:invoices:read"))])
async def list_invoices(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("finance", "invoices")
    total_stmt = select(func.count()).select_from(FinanceInvoice).where(FinanceInvoice.is_deleted == False)
    total = (await session.execute(total_stmt)).scalar() or 0

    items = await invoice_service.get_all_invoices(session, skip=pagination.offset, limit=pagination.limit)
    return paginated_response(data=items, total=total, page=pagination.page, page_size=pagination.page_size)


@router.get("/invoices/{id}", dependencies=[Depends(require_permission("finance:invoices:read"))])
async def get_invoice(id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("finance", "invoices")
    invoice = await invoice_service.get_invoice(session, id)
    if not invoice:
        raise HTTPException(status_code=404, detail=f"Invoice with ID {id} not found.")
    return success_response(data=invoice)


@router.post("/invoices/{id}/issue", dependencies=[Depends(require_permission("finance:invoices:write"))])
async def issue_invoice(id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("finance", "invoices")
    try:
        invoice = await invoice_service.issue_invoice(session, id)
        return success_response(data=invoice)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    except StateTransitionError as e:
        raise HTTPException(status_code=422, detail=e.message)


# --- Payment Endpoints ---

@router.post("/payments", dependencies=[Depends(require_permission("finance:payments:write"))])
async def record_payment(
    data: FinancePaymentCreate,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("finance", "payments")
    try:
        payment = await payment_service.record_payment(session, data)
        return success_response(data=payment)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)


@router.get("/payments", dependencies=[Depends(require_permission("finance:payments:read"))])
async def list_payments(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("finance", "payments")
    total_stmt = select(func.count()).select_from(FinancePayment).where(FinancePayment.is_deleted == False)
    total = (await session.execute(total_stmt)).scalar() or 0

    items = await payment_service.get_all_payments(session, skip=pagination.offset, limit=pagination.limit)
    return paginated_response(data=items, total=total, page=pagination.page, page_size=pagination.page_size)


@router.get("/payments/{id}", dependencies=[Depends(require_permission("finance:payments:read"))])
async def get_payment(id: uuid.UUID, session: AsyncSession = Depends(get_async_session)):
    require_licensed_feature("finance", "payments")
    payment = await payment_service.get_payment(session, id)
    if not payment:
        raise HTTPException(status_code=404, detail=f"Payment with ID {id} not found.")
    return success_response(data=payment)
