import logging
import uuid
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError
from sqlmodel import select, func

from core import Customer, Role, NotificationRule
from core.exceptions import ConcurrencyError
from core.pagination import PaginationParams

from .models import CustomerAddress, CustomerContact, CustomerCredit
from .schemas import (
    CustomerCreate,
    CustomerUpdate,
    CustomerAddressCreate,
    CustomerAddressUpdate,
    CustomerContactCreate,
    CustomerContactUpdate,
    CustomerCreditUpdate
)
from .events import (
    emit_customer_created,
    emit_customer_credit_hold,
    emit_customer_credit_released
)

logger = logging.getLogger(__name__)


# --- Notification Rule Seeding Helper ---
async def seed_sales_notification_rules(session: AsyncSession):
    """
    Seeds default notification rules for Customer Master events if not already present.
    Ensures correct system setups for credit hold notifications.
    """
    # Attempt to locate finance controller role for recipient target fallback
    role_stmt = select(Role).where(Role.name == "finance_controller")
    role_res = await session.execute(role_stmt)
    finance_controller_role = role_res.scalars().first()
    recipient_target_id = str(finance_controller_role.id) if finance_controller_role else "finance_controller"

    # Query for existing rules
    existing_stmt = select(NotificationRule).where(
        NotificationRule.event_type.in_(["CUSTOMER_CREDIT_HOLD", "CUSTOMER_CREDIT_RELEASED"])
    )
    existing_res = await session.execute(existing_stmt)
    existing_rules = existing_res.scalars().all()

    if not existing_rules:
        logger.info("[Sales] Seeding default Customer Master NotificationRule settings.")
        rule_hold = NotificationRule(
            event_type="CUSTOMER_CREDIT_HOLD",
            channel="EMAIL",
            recipient_type="ROLE",
            recipient_target=recipient_target_id,
            template_title="Credit Hold: Customer {{ customer_name }}",
            template_body="Sales order {{ order_id }} for {{ customer_name }} has been placed on credit hold because the order amount of {{ order_amount }} exceeds the available credit of {{ available_credit }}."
        )
        rule_release = NotificationRule(
            event_type="CUSTOMER_CREDIT_RELEASED",
            channel="IN_APP",
            recipient_type="DYNAMIC_PATH",
            recipient_target="$.data.sales_rep_id",
            template_title="Credit Hold Released: {{ customer_name }}",
            template_body="The credit hold on sales order {{ order_id }} for {{ customer_name }} has been manually released by user {{ authorizer_name }}."
        )
        session.add(rule_hold)
        session.add(rule_release)
        await session.commit()


# --- Customer Card Profile Services ---

async def list_customers(session: AsyncSession, pagination: PaginationParams) -> Tuple[List[Customer], int]:
    """
    Retrieve active customer records with pagination.
    Also ensures default notification rules are auto-seeded.
    """
    await seed_sales_notification_rules(session)

    count_stmt = select(func.count()).select_from(Customer).where(Customer.is_deleted == False)
    total = (await session.execute(count_stmt)).scalar() or 0

    stmt = (
        select(Customer)
        .where(Customer.is_deleted == False)
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    result = await session.execute(stmt)
    items = result.scalars().all()
    return list(items), total


async def get_customer(session: AsyncSession, customer_id: uuid.UUID) -> Optional[Customer]:
    """Retrieve a single active customer card by ID."""
    stmt = select(Customer).where(Customer.id == customer_id, Customer.is_deleted == False)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_customer(session: AsyncSession, data: CustomerCreate) -> Customer:
    """
    Create a new customer master card.
    Automatically provisions an empty customer credit account.
    Emits the CUSTOMER_CREATED event.
    """
    # 1. Create the customer card
    customer = Customer(
        name=data.name,
        tax_id=data.tax_id,
        primary_email=data.primary_email,
        parent_customer_id=data.parent_customer_id
    )
    session.add(customer)
    await session.commit()
    await session.refresh(customer)

    # 2. Provision default CustomerCredit profile
    credit = CustomerCredit(
        customer_id=customer.id,
        credit_limit=0.0000,
        outstanding_balance=0.0000,
        status="ACTIVE"
    )
    session.add(credit)
    await session.commit()

    # 3. Emit creation event
    await emit_customer_created(customer_id=str(customer.id), customer_name=customer.name)

    return customer


async def update_customer(session: AsyncSession, customer_id: uuid.UUID, data: CustomerUpdate) -> Customer:
    """
    Update customer card attributes under optimistic locking version control.
    """
    stmt = select(Customer).where(Customer.id == customer_id, Customer.is_deleted == False)
    result = await session.execute(stmt)
    customer = result.scalar_one_or_none()

    if not customer:
        raise ValueError("Customer not found")

    # Optimistic locking check
    if customer.version_id != data.version_id:
         raise ConcurrencyError("The customer card was modified by another administrator. Please refresh.")

    # Update fields if provided
    update_dict = data.model_dump(exclude_unset=True, exclude={"version_id"})
    for key, value in update_dict.items():
        setattr(customer, key, value)

    session.add(customer)
    try:
        await session.commit()
        await session.refresh(customer)
    except StaleDataError:
        await session.rollback()
        raise ConcurrencyError("Customer was concurrently updated by another user.")

    return customer


async def delete_customer(session: AsyncSession, customer_id: uuid.UUID) -> None:
    """
    Soft-delete a customer and all nested address, contact, and credit cards.
    """
    stmt = select(Customer).where(Customer.id == customer_id, Customer.is_deleted == False)
    result = await session.execute(stmt)
    customer = result.scalar_one_or_none()

    if not customer:
        raise ValueError("Customer not found")

    # Soft-delete parent card
    customer.is_deleted = True
    session.add(customer)

    # Soft-delete child addresses
    addr_stmt = select(CustomerAddress).where(CustomerAddress.customer_id == customer_id, CustomerAddress.is_deleted == False)
    addr_result = await session.execute(addr_stmt)
    for addr in addr_result.scalars().all():
        addr.is_deleted = True
        session.add(addr)

    # Soft-delete child contacts
    cont_stmt = select(CustomerContact).where(CustomerContact.customer_id == customer_id, CustomerContact.is_deleted == False)
    cont_result = await session.execute(cont_stmt)
    for cont in cont_result.scalars().all():
        cont.is_deleted = True
        session.add(cont)

    # Soft-delete credit records
    cred_stmt = select(CustomerCredit).where(CustomerCredit.customer_id == customer_id, CustomerCredit.is_deleted == False)
    cred_result = await session.execute(cred_stmt)
    for cred in cred_result.scalars().all():
        cred.is_deleted = True
        session.add(cred)

    await session.commit()


# --- Customer Address Services ---

async def list_customer_addresses(session: AsyncSession, customer_id: uuid.UUID) -> List[CustomerAddress]:
    """Retrieve active address profiles for a customer."""
    stmt = select(CustomerAddress).where(
        CustomerAddress.customer_id == customer_id,
        CustomerAddress.is_deleted == False
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_customer_address(session: AsyncSession, customer_id: uuid.UUID, data: CustomerAddressCreate) -> CustomerAddress:
    """
    Create a shipping/billing address.
    If is_default is true, unsets defaults for same address type.
    """
    if data.is_default:
        # Clear existing default of same type
        stmt = select(CustomerAddress).where(
            CustomerAddress.customer_id == customer_id,
            CustomerAddress.address_type == data.address_type,
            CustomerAddress.is_default == True,
            CustomerAddress.is_deleted == False
        )
        existing_res = await session.execute(stmt)
        for addr in existing_res.scalars().all():
            addr.is_default = False
            session.add(addr)

    db_obj = CustomerAddress(
        customer_id=customer_id,
        address_type=data.address_type,
        street_address=data.street_address,
        city=data.city,
        state=data.state,
        postal_code=data.postal_code,
        country_code=data.country_code,
        is_default=data.is_default
    )
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


async def update_customer_address(session: AsyncSession, address_id: uuid.UUID, data: CustomerAddressUpdate) -> CustomerAddress:
    """Update address credentials under optimistic locking control."""
    stmt = select(CustomerAddress).where(CustomerAddress.id == address_id, CustomerAddress.is_deleted == False)
    result = await session.execute(stmt)
    address = result.scalar_one_or_none()

    if not address:
        raise ValueError("Address not found")

    if address.version_id != data.version_id:
        raise ConcurrencyError("The address card was modified concurrently. Please refresh.")

    if data.is_default:
        # Reset defaults for other addresses of the same type
        addr_type = data.address_type or address.address_type
        clear_stmt = select(CustomerAddress).where(
            CustomerAddress.customer_id == address.customer_id,
            CustomerAddress.address_type == addr_type,
            CustomerAddress.is_default == True,
            CustomerAddress.is_deleted == False
        )
        existing_res = await session.execute(clear_stmt)
        for other in existing_res.scalars().all():
            if other.id != address.id:
                other.is_default = False
                session.add(other)

    update_dict = data.model_dump(exclude_unset=True, exclude={"version_id"})
    for key, value in update_dict.items():
        setattr(address, key, value)

    session.add(address)
    try:
        await session.commit()
        await session.refresh(address)
    except StaleDataError:
        await session.rollback()
        raise ConcurrencyError("Address card was concurrently updated.")

    return address


async def delete_customer_address(session: AsyncSession, address_id: uuid.UUID) -> None:
    """Soft-delete an address profile card."""
    stmt = select(CustomerAddress).where(CustomerAddress.id == address_id, CustomerAddress.is_deleted == False)
    result = await session.execute(stmt)
    address = result.scalar_one_or_none()

    if not address:
        raise ValueError("Address not found")

    address.is_deleted = True
    session.add(address)
    await session.commit()


# --- Customer Contacts Services ---

async def list_customer_contacts(session: AsyncSession, customer_id: uuid.UUID) -> List[CustomerContact]:
    """Retrieve active contact directories representing a customer."""
    stmt = select(CustomerContact).where(
        CustomerContact.customer_id == customer_id,
        CustomerContact.is_deleted == False
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_customer_contact(session: AsyncSession, customer_id: uuid.UUID, data: CustomerContactCreate) -> CustomerContact:
    """Add a contact directory member to a customer."""
    db_obj = CustomerContact(
        customer_id=customer_id,
        first_name=data.first_name,
        last_name=data.last_name,
        email=data.email,
        phone=data.phone,
        department=data.department
    )
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


async def update_customer_contact(session: AsyncSession, contact_id: uuid.UUID, data: CustomerContactUpdate) -> CustomerContact:
    """Update contact credentials with optimistic locking."""
    stmt = select(CustomerContact).where(CustomerContact.id == contact_id, CustomerContact.is_deleted == False)
    result = await session.execute(stmt)
    contact = result.scalar_one_or_none()

    if not contact:
        raise ValueError("Contact not found")

    if contact.version_id != data.version_id:
        raise ConcurrencyError("The contact was updated concurrently. Please refresh.")

    update_dict = data.model_dump(exclude_unset=True, exclude={"version_id"})
    for key, value in update_dict.items():
        setattr(contact, key, value)

    session.add(contact)
    try:
        await session.commit()
        await session.refresh(contact)
    except StaleDataError:
        await session.rollback()
        raise ConcurrencyError("Contact card updated concurrently.")

    return contact


async def delete_customer_contact(session: AsyncSession, contact_id: uuid.UUID) -> None:
    """Soft-delete a customer representative directory card."""
    stmt = select(CustomerContact).where(CustomerContact.id == contact_id, CustomerContact.is_deleted == False)
    result = await session.execute(stmt)
    contact = result.scalar_one_or_none()

    if not contact:
        raise ValueError("Contact not found")

    contact.is_deleted = True
    session.add(contact)
    await session.commit()


# --- Customer Credit & Risk Management Services ---

async def get_customer_credit(session: AsyncSession, customer_id: uuid.UUID) -> CustomerCredit:
    """
    Get customer credit profile.
    Automatically seeds/provisions defaults if missing.
    """
    stmt = select(CustomerCredit).where(
        CustomerCredit.customer_id == customer_id,
        CustomerCredit.is_deleted == False
    )
    result = await session.execute(stmt)
    credit = result.scalar_one_or_none()

    if not credit:
        # Auto-provision credit registry if absent
        credit = CustomerCredit(
            customer_id=customer_id,
            credit_limit=0.0000,
            outstanding_balance=0.0000,
            status="ACTIVE"
        )
        session.add(credit)
        await session.commit()
        await session.refresh(credit)

    return credit


async def update_customer_credit(session: AsyncSession, customer_id: uuid.UUID, data: CustomerCreditUpdate) -> CustomerCredit:
    """
    Update credit boundaries and net payment terms configurations.
    Uses optimistic locking control.
    """
    credit = await get_customer_credit(session, customer_id)

    if credit.version_id != data.version_id:
        raise ConcurrencyError("Credit rules were modified by another accountant. Please refresh.")

    credit.credit_limit = data.credit_limit
    if data.payment_terms_code is not None:
        credit.payment_terms_code = data.payment_terms_code

    session.add(credit)
    try:
        await session.commit()
        await session.refresh(credit)
    except StaleDataError:
        await session.rollback()
        raise ConcurrencyError("Credit balance updated concurrently.")

    return credit


async def execute_credit_override(session: AsyncSession, order_id: uuid.UUID, customer_id: uuid.UUID, authorizer_name: str) -> CustomerCredit:
    """
    Overrides and releases a credit hold on a specific sales order.
    Pessimistic Locking: fetches customer's credit record with a write-lock (SELECT FOR UPDATE)
    to block concurrent adjustments.
    Emits CUSTOMER_CREDIT_RELEASED pub/sub signal.
    """
    # 1. Pessimistic Write Lock
    stmt = select(CustomerCredit).where(
        CustomerCredit.customer_id == customer_id,
        CustomerCredit.is_deleted == False
    ).with_for_update()
    result = await session.execute(stmt)
    credit = result.scalar_one_or_none()

    if not credit:
        raise ValueError("Customer credit profile not found.")

    # 2. Release hold status
    credit.status = "ACTIVE"
    session.add(credit)
    await session.commit()
    await session.refresh(credit)

    # 3. Retrieve Customer details for event payload
    cust_stmt = select(Customer).where(Customer.id == customer_id)
    cust_res = await session.execute(cust_stmt)
    customer = cust_res.scalar_one_or_none()
    customer_name = customer.name if customer else "Unknown Customer"

    # 4. Emit event
    await emit_customer_credit_released(
        customer_id=str(customer_id),
        customer_name=customer_name,
        order_id=str(order_id),
        authorizer_name=authorizer_name
    )

    return credit
