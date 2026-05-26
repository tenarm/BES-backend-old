import logging
import uuid
from typing import Optional, List, Tuple
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func, or_
from core.models import Customer
from core.exceptions import ConcurrencyError
from core.events import event_bus, BaseEventPayload

from .models import SalesCustomerDetails, SalesCustomerAddress, SalesCustomerContact
from .schemas import (
    CustomerCommercialOnboard, CustomerCommercialUpdate, CustomerCommercialRead,
    SalesCustomerAddressRead, SalesCustomerContactRead
)

logger = logging.getLogger(__name__)

# --- Business Exceptions per Rule 1.14 ---
class DuplicateTaxRegistrationError(Exception):
    """Raised when onboarding a customer with a Tax ID that already exists in core."""
    pass

class InvalidCreditLimitError(Exception):
    """Raised when a negative credit limit or invalid decimal scale is provided."""
    pass

class UnsupportedCurrencyError(Exception):
    """Raised when an invalid ISO currency code is provided."""
    pass

class CustomerNotFoundError(Exception):
    """Raised when customer is not found."""
    pass

class CustomerSalesService:
    @staticmethod
    async def _to_commercial_read(
        session: AsyncSession, 
        customer: Customer, 
        details: Optional[SalesCustomerDetails]
    ) -> CustomerCommercialRead:
        """Helper to retrieve child records and build full read schema."""
        # Query addresses
        addr_stmt = select(SalesCustomerAddress).where(
            SalesCustomerAddress.customer_id == customer.id,
            SalesCustomerAddress.is_deleted == False
        )
        addr_res = await session.execute(addr_stmt)
        addresses = addr_res.scalars().all()

        # Query contacts
        contact_stmt = select(SalesCustomerContact).where(
            SalesCustomerContact.customer_id == customer.id,
            SalesCustomerContact.is_deleted == False
        )
        contact_res = await session.execute(contact_stmt)
        contacts = contact_res.scalars().all()

        return CustomerCommercialRead(
            id=customer.id,
            name=customer.name,
            tax_id=customer.tax_id,
            primary_email=customer.primary_email,
            version_id=customer.version_id,
            credit_limit=details.credit_limit if details else Decimal("0.0"),
            payment_terms=details.payment_terms if details else "Net 30",
            currency=details.currency if details else "USD",
            credit_hold=details.credit_hold if details else False,
            notes=details.notes if details else None,
            addresses=[
                SalesCustomerAddressRead(
                    id=a.id, customer_id=a.customer_id, address_type=a.address_type,
                    address_line1=a.address_line1, address_line2=a.address_line2,
                    city=a.city, state=a.state, postal_code=a.postal_code,
                    country=a.country, is_primary=a.is_primary
                ) for a in addresses
            ],
            contacts=[
                SalesCustomerContactRead(
                    id=c.id, customer_id=c.customer_id, full_name=c.full_name,
                    email=c.email, phone=c.phone, role=c.role
                ) for c in contacts
            ]
        )

    @staticmethod
    async def onboard_customer(
        session: AsyncSession, 
        data: CustomerCommercialOnboard,
        created_by: Optional[uuid.UUID] = None
    ) -> CustomerCommercialRead:
        """
        Creates a customer base profile in core, initializes sales commercial extension,
        and saves child address and contact models under a single transaction.
        """
        # 1. Domain Validations
        if data.credit_limit < Decimal("0.0"):
            raise InvalidCreditLimitError("Credit limit must be greater than or equal to 0.0000.")

        if len(data.currency) != 3:
            raise UnsupportedCurrencyError("Currency must be a valid 3-letter ISO code.")

        # Check unique tax ID in core Customer table
        if data.tax_id:
            tax_stmt = select(Customer).where(
                Customer.tax_id == data.tax_id,
                Customer.is_deleted == False
            )
            tax_res = await session.execute(tax_stmt)
            if tax_res.scalars().first():
                raise DuplicateTaxRegistrationError(f"Tax registration ID '{data.tax_id}' already exists in core.")

        created_by_str = str(created_by) if created_by else None

        # 2. Database Mutations
        # Write base customer
        customer = Customer(
            name=data.name,
            tax_id=data.tax_id,
            primary_email=data.primary_email,
            created_by=created_by_str,
            version_id=1
        )
        session.add(customer)
        await session.flush()  # Generate customer.id

        # Write sales commercial details
        details = SalesCustomerDetails(
            customer_id=customer.id,
            credit_limit=data.credit_limit,
            payment_terms=data.payment_terms,
            currency=data.currency,
            credit_hold=False,
            notes=data.notes,
            created_by=created_by_str
        )
        session.add(details)

        # Write addresses
        for addr in data.addresses:
            db_addr = SalesCustomerAddress(
                customer_id=customer.id,
                address_type=addr.address_type,
                address_line1=addr.address_line1,
                address_line2=addr.address_line2,
                city=addr.city,
                state=addr.state,
                postal_code=addr.postal_code,
                country=addr.country,
                is_primary=addr.is_primary,
                created_by=created_by_str
            )
            session.add(db_addr)

        # Write contacts
        for contact in data.contacts:
            db_contact = SalesCustomerContact(
                customer_id=customer.id,
                full_name=contact.full_name,
                email=contact.email,
                phone=contact.phone,
                role=contact.role,
                created_by=created_by_str
            )
            session.add(db_contact)

        await session.commit()
        await session.refresh(customer)
        await session.refresh(details)

        # 3. Post-Commit Event Dispatching (Rule 1.14: Safe post-commit events)
        try:
            payload = BaseEventPayload(
                emitter_module="sales",
                event_type="CUSTOMER_ONBOARDED",
                data={
                    "customer_id": str(customer.id),
                    "name": customer.name,
                    "tax_id": customer.tax_id,
                    "created_by": created_by_str
                }
            )
            await event_bus.emit(payload)
        except Exception as e:
            logger.error(f"Failed to emit CUSTOMER_ONBOARDED event: {e}")

        return await CustomerSalesService._to_commercial_read(session, customer, details)

    @staticmethod
    async def update_customer(
        session: AsyncSession,
        customer_id: uuid.UUID,
        data: CustomerCommercialUpdate,
        version_id: int,
        updated_by: Optional[uuid.UUID] = None
    ) -> CustomerCommercialRead:
        """
        Updates core customer profiles and commercial fields under a shared transaction,
        validating version_id for optimistic locking concurrency control.
        """
        # Fetch core customer
        cust_stmt = select(Customer).where(Customer.id == customer_id, Customer.is_deleted == False)
        cust_res = await session.execute(cust_stmt)
        customer = cust_res.scalars().first()
        if not customer:
            raise CustomerNotFoundError(f"Customer with ID '{customer_id}' not found.")

        # Optimistic Locking Check
        if customer.version_id != version_id:
            raise ConcurrencyError(
                f"Concurrency Conflict: Customer record has been updated by another user (expected version: {version_id}, actual version: {customer.version_id})."
            )

        updated_by_str = str(updated_by) if updated_by else None

        # Fetch sales details
        details_stmt = select(SalesCustomerDetails).where(
            SalesCustomerDetails.customer_id == customer_id,
            SalesCustomerDetails.is_deleted == False
        )
        details_res = await session.execute(details_stmt)
        details = details_res.scalars().first()
        if not details:
            # If not initialized, initialize it now
            details = SalesCustomerDetails(customer_id=customer_id, created_by=updated_by_str)
            session.add(details)

        # 1. Domain Validations
        if data.credit_limit is not None and data.credit_limit < Decimal("0.0"):
            raise InvalidCreditLimitError("Credit limit must be greater than or equal to 0.0000.")

        if data.currency is not None and len(data.currency) != 3:
            raise UnsupportedCurrencyError("Currency must be a valid 3-letter ISO code.")

        # 2. Database Mutations
        # Update core fields
        if data.name is not None:
            customer.name = data.name
        if data.tax_id is not None:
            customer.tax_id = data.tax_id
        if data.primary_email is not None:
            customer.primary_email = data.primary_email
        
        customer.version_id += 1  # Increment version

        # Update sales details
        if data.credit_limit is not None:
            details.credit_limit = data.credit_limit
        if data.payment_terms is not None:
            details.payment_terms = data.payment_terms
        if data.currency is not None:
            details.currency = data.currency
        if data.credit_hold is not None:
            details.credit_hold = data.credit_hold
        if data.notes is not None:
            details.notes = data.notes

        # Handle addresses override if provided
        if data.addresses is not None:
            # Soft delete old addresses
            del_addr_stmt = select(SalesCustomerAddress).where(
                SalesCustomerAddress.customer_id == customer_id,
                SalesCustomerAddress.is_deleted == False
            )
            del_addr_res = await session.execute(del_addr_stmt)
            for addr in del_addr_res.scalars().all():
                addr.is_deleted = True

            # Insert new addresses
            for addr in data.addresses:
                db_addr = SalesCustomerAddress(
                    customer_id=customer_id,
                    address_type=addr.address_type,
                    address_line1=addr.address_line1,
                    address_line2=addr.address_line2,
                    city=addr.city,
                    state=addr.state,
                    postal_code=addr.postal_code,
                    country=addr.country,
                    is_primary=addr.is_primary,
                    created_by=updated_by_str
                )
                session.add(db_addr)

        # Handle contacts override if provided
        if data.contacts is not None:
            # Soft delete old contacts
            del_contact_stmt = select(SalesCustomerContact).where(
                SalesCustomerContact.customer_id == customer_id,
                SalesCustomerContact.is_deleted == False
            )
            del_contact_res = await session.execute(del_contact_stmt)
            for contact in del_contact_res.scalars().all():
                contact.is_deleted = True

            # Insert new contacts
            for contact in data.contacts:
                db_contact = SalesCustomerContact(
                    customer_id=customer_id,
                    full_name=contact.full_name,
                    email=contact.email,
                    phone=contact.phone,
                    role=contact.role,
                    created_by=updated_by_str
                )
                session.add(db_contact)

        await session.commit()
        await session.refresh(customer)
        await session.refresh(details)

        # 3. Post-Commit Event Dispatching
        try:
            payload = BaseEventPayload(
                emitter_module="sales",
                event_type="CUSTOMER_COMMERCIAL_UPDATED",
                data={
                    "customer_id": str(customer_id),
                    "name": customer.name,
                    "credit_limit": str(details.credit_limit),
                    "credit_hold": details.credit_hold,
                    "updated_by": updated_by_str
                }
            )
            await event_bus.emit(payload)
        except Exception as e:
            logger.error(f"Failed to emit CUSTOMER_COMMERCIAL_UPDATED event: {e}")

        return await CustomerSalesService._to_commercial_read(session, customer, details)

    @staticmethod
    async def check_credit_eligibility(
        session: AsyncSession,
        customer_id: uuid.UUID,
        order_amount: Decimal
    ) -> bool:
        """
        Executes a pessimistic read lock on a customer's commercial profile row
        to prevent concurrent checkout attempts from bypassing credit checking thresholds.
        """
        # Fetch commercial profile with FOR UPDATE pessimistic lock
        stmt = select(SalesCustomerDetails).where(
            SalesCustomerDetails.customer_id == customer_id,
            SalesCustomerDetails.is_deleted == False
        ).with_for_update()
        res = await session.execute(stmt)
        details = res.scalars().first()
        if not details:
            return True

        if details.credit_hold:
            return False

        if details.credit_limit == Decimal("0.0"):
            return True

        # Calculate outstanding receivables
        receivables = Decimal("0.0")
        try:
            ar_stmt = text(
                "SELECT SUM(grand_total - paid_amount) FROM finance_sales_invoices "
                "WHERE customer_id = :cust_id AND is_deleted = False AND is_posted = True"
            )
            ar_res = await session.execute(ar_stmt, {"cust_id": str(customer_id)})
            receivables = ar_res.scalar() or Decimal("0.0")
        except Exception:
            pass

        # Calculate pending un-invoiced orders
        pending_orders = Decimal("0.0")
        try:
            order_stmt = text(
                "SELECT SUM(grand_total) FROM sales_orders "
                "WHERE customer_id = :cust_id AND is_deleted = False AND status = 'Approved'"
            )
            order_res = await session.execute(order_stmt, {"cust_id": str(customer_id)})
            pending_orders = order_res.scalar() or Decimal("0.0")
        except Exception:
            pass

        # Compute available credit quantized to 4 decimal places
        total_risk = (receivables + pending_orders + order_amount).quantize(
            Decimal("0.0001")
        )

        if total_risk > details.credit_limit:
            # Trigger credit hold
            details.credit_hold = True
            await session.commit()
            
            # Post-commit event trigger
            try:
                payload = BaseEventPayload(
                    emitter_module="sales",
                    event_type="CUSTOMER_CREDIT_HOLD_TRIGGERED",
                    data={
                        "customer_id": str(customer_id),
                        "outstanding_receivables": str(receivables),
                        "pending_orders": str(pending_orders),
                        "order_amount": str(order_amount),
                        "credit_limit": str(details.credit_limit)
                    }
                )
                await event_bus.emit(payload)
            except Exception as e:
                logger.error(f"Failed to emit CUSTOMER_CREDIT_HOLD_TRIGGERED: {e}")
            return False

        return True

    @staticmethod
    async def list_customers(
        session: AsyncSession,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[CustomerCommercialRead], int]:
        """Paginated list query combining core Customer and Sales extensions."""
        count_query = select(func.count(Customer.id)).where(Customer.is_deleted == False)
        if search:
            count_query = count_query.where(
                or_(
                    Customer.name.ilike(f"%{search}%"),
                    Customer.tax_id.ilike(f"%{search}%"),
                    Customer.primary_email.ilike(f"%{search}%")
                )
            )
        total = (await session.execute(count_query)).scalar() or 0

        stmt = select(Customer).where(Customer.is_deleted == False)
        if search:
            stmt = stmt.where(
                or_(
                    Customer.name.ilike(f"%{search}%"),
                    Customer.tax_id.ilike(f"%{search}%"),
                    Customer.primary_email.ilike(f"%{search}%")
                )
            )
        
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)
        res = await session.execute(stmt)
        customers = res.scalars().all()

        items = []
        for cust in customers:
            details_stmt = select(SalesCustomerDetails).where(
                SalesCustomerDetails.customer_id == cust.id,
                SalesCustomerDetails.is_deleted == False
            )
            d_res = await session.execute(details_stmt)
            details = d_res.scalars().first()
            
            items.append(await CustomerSalesService._to_commercial_read(session, cust, details))

        return items, total

    @staticmethod
    async def get_customer(session: AsyncSession, customer_id: uuid.UUID) -> Optional[CustomerCommercialRead]:
        """Retrieves a single unified customer record by ID."""
        cust_stmt = select(Customer).where(Customer.id == customer_id, Customer.is_deleted == False)
        cust_res = await session.execute(cust_stmt)
        customer = cust_res.scalars().first()
        if not customer:
            return None

        details_stmt = select(SalesCustomerDetails).where(
            SalesCustomerDetails.customer_id == customer_id,
            SalesCustomerDetails.is_deleted == False
        )
        d_res = await session.execute(details_stmt)
        details = d_res.scalars().first()

        return await CustomerSalesService._to_commercial_read(session, customer, details)

    @staticmethod
    async def toggle_credit_hold(
        session: AsyncSession, 
        customer_id: uuid.UUID, 
        credit_hold: bool,
        updated_by: Optional[uuid.UUID] = None
    ) -> CustomerCommercialRead:
        """Manually unlocks or overrides the active credit blockage state."""
        cust_stmt = select(Customer).where(Customer.id == customer_id, Customer.is_deleted == False)
        cust_res = await session.execute(cust_stmt)
        customer = cust_res.scalars().first()
        if not customer:
            raise CustomerNotFoundError(f"Customer with ID '{customer_id}' not found.")

        updated_by_str = str(updated_by) if updated_by else None

        details_stmt = select(SalesCustomerDetails).where(
            SalesCustomerDetails.customer_id == customer_id,
            SalesCustomerDetails.is_deleted == False
        )
        d_res = await session.execute(details_stmt)
        details = d_res.scalars().first()
        if not details:
            details = SalesCustomerDetails(customer_id=customer_id, created_by=updated_by_str)
            session.add(details)

        details.credit_hold = credit_hold
        
        await session.commit()
        await session.refresh(customer)
        await session.refresh(details)

        return await CustomerSalesService._to_commercial_read(session, customer, details)


async def create_entity(session: AsyncSession, data) -> "SalesEntity":
    """Creates a basic sales entity record."""
    from .models import SalesEntity
    db_obj = SalesEntity.model_validate(data)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj

