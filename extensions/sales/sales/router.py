import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func
from pydantic import BaseModel

from core.database import get_async_session
from core.responses import success_response, paginated_response
from core.pagination import PaginationParams
from core.licensing import require_licensed_feature
from core.rbac import require_permission
from core.auth import get_current_user
from core.models import User

from .models import CustomerAddress, CustomerContact
from .schemas import (
    CustomerCreate,
    CustomerUpdate,
    CustomerAddressCreate,
    CustomerAddressUpdate,
    CustomerContactCreate,
    CustomerContactUpdate,
    CustomerCreditUpdate
)
from .services import (
    list_customers,
    get_customer,
    create_customer,
    update_customer,
    delete_customer,
    list_customer_addresses,
    create_customer_address,
    update_customer_address,
    delete_customer_address,
    list_customer_contacts,
    create_customer_contact,
    update_customer_contact,
    delete_customer_contact,
    get_customer_credit,
    update_customer_credit,
    execute_credit_override
)

router = APIRouter(prefix="/api/v1/sales", tags=["Customer Master"])


# --- Request Payloads ---
class CreditOverridePayload(BaseModel):
    customer_id: uuid.UUID


# --- Customer Profiling Endpoints ---

@router.get("/customers", dependencies=[Depends(require_permission("sales:customer:read"))])
async def list_customers_endpoint(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "customer_master")
    items, total = await list_customers(session, pagination)
    return paginated_response(
        data=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size
    )


@router.get("/customers/{id}", dependencies=[Depends(require_permission("sales:customer:read"))])
async def get_customer_endpoint(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "customer_master")
    customer = await get_customer(session, id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return success_response(data=customer)


@router.post("/customers", dependencies=[Depends(require_permission("sales:customer:write"))])
async def create_customer_endpoint(
    data: CustomerCreate,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "customer_master")
    customer = await create_customer(session, data)
    return success_response(data=customer)


@router.put("/customers/{id}", dependencies=[Depends(require_permission("sales:customer:write"))])
async def update_customer_endpoint(
    id: uuid.UUID,
    data: CustomerUpdate,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "customer_master")
    try:
        customer = await update_customer(session, id, data)
        return success_response(data=customer)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/customers/{id}", dependencies=[Depends(require_permission("sales:customer:write"))])
async def delete_customer_endpoint(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "customer_master")
    try:
        await delete_customer(session, id)
        return success_response(data={"detail": "Customer deleted successfully"})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Customer Address Endpoints ---

@router.get("/customers/{id}/addresses", dependencies=[Depends(require_permission("sales:customer:read"))])
async def list_customer_addresses_endpoint(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "customer_master")
    addresses = await list_customer_addresses(session, id)
    return success_response(data=addresses)


@router.post("/customers/{id}/addresses", dependencies=[Depends(require_permission("sales:customer:write"))])
async def create_customer_address_endpoint(
    id: uuid.UUID,
    data: CustomerAddressCreate,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "customer_master")

    # Check count of existing active addresses for multi-address licensing gate
    stmt = select(func.count()).select_from(CustomerAddress).where(
        CustomerAddress.customer_id == id,
        CustomerAddress.is_deleted == False
    )
    res = await session.execute(stmt)
    count = res.scalar() or 0

    if count >= 1:
        # Require 'multi_address' feature tier for secondary shipping/billing sites
        require_licensed_feature("sales", "multi_address")

    address = await create_customer_address(session, id, data)
    return success_response(data=address)


@router.put("/customers/addresses/{address_id}", dependencies=[Depends(require_permission("sales:customer:write"))])
async def update_customer_address_endpoint(
    address_id: uuid.UUID,
    data: CustomerAddressUpdate,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "customer_master")
    try:
        address = await update_customer_address(session, address_id, data)
        return success_response(data=address)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/customers/addresses/{address_id}", dependencies=[Depends(require_permission("sales:customer:write"))])
async def delete_customer_address_endpoint(
    address_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "customer_master")
    try:
        await delete_customer_address(session, address_id)
        return success_response(data={"detail": "Address deleted successfully"})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Customer Contact Endpoints ---

@router.get("/customers/{id}/contacts", dependencies=[Depends(require_permission("sales:customer:read"))])
async def list_customer_contacts_endpoint(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "customer_master")
    contacts = await list_customer_contacts(session, id)
    return success_response(data=contacts)


@router.post("/customers/{id}/contacts", dependencies=[Depends(require_permission("sales:customer:write"))])
async def create_customer_contact_endpoint(
    id: uuid.UUID,
    data: CustomerContactCreate,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "customer_master")
    contact = await create_customer_contact(session, id, data)
    return success_response(data=contact)


@router.put("/customers/contacts/{contact_id}", dependencies=[Depends(require_permission("sales:customer:write"))])
async def update_customer_contact_endpoint(
    contact_id: uuid.UUID,
    data: CustomerContactUpdate,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "customer_master")
    try:
        contact = await update_customer_contact(session, contact_id, data)
        return success_response(data=contact)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/customers/contacts/{contact_id}", dependencies=[Depends(require_permission("sales:customer:write"))])
async def delete_customer_contact_endpoint(
    contact_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "customer_master")
    try:
        await delete_customer_contact(session, contact_id)
        return success_response(data={"detail": "Contact deleted successfully"})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Credit Profile Endpoints ---

@router.get("/customers/{id}/credit", dependencies=[Depends(require_permission("sales:credit:read"))])
async def get_customer_credit_endpoint(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "credit_management")
    credit = await get_customer_credit(session, id)
    return success_response(data=credit)


@router.put("/customers/{id}/credit", dependencies=[Depends(require_permission("sales:credit:write"))])
async def update_customer_credit_endpoint(
    id: uuid.UUID,
    data: CustomerCreditUpdate,
    session: AsyncSession = Depends(get_async_session)
):
    require_licensed_feature("sales", "credit_management")
    try:
        credit = await update_customer_credit(session, id, data)
        return success_response(data=credit)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/customers/credit-override/{order_id}", dependencies=[Depends(require_permission("sales:credit:write"))])
async def execute_credit_override_endpoint(
    order_id: uuid.UUID,
    payload: CreditOverridePayload,
    session: AsyncSession = Depends(get_async_session),
    current_user: User = Depends(get_current_user)
):
    """
    Override and release the credit hold on a specific sales order.
    Executes under pessimistic locking control.
    """
    require_licensed_feature("sales", "credit_management")
    authorizer_name = current_user.full_name or current_user.username
    try:
        credit = await execute_credit_override(
            session=session,
            order_id=order_id,
            customer_id=payload.customer_id,
            authorizer_name=authorizer_name
        )
        return success_response(data=credit)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
