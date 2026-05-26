import pytest
import uuid
from decimal import Decimal
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Customer
from sales.models import SalesCustomerDetails, SalesCustomerAddress, SalesCustomerContact
from sales.schemas import (
    CustomerCommercialOnboard, CustomerCommercialUpdate,
    SalesCustomerAddressCreate, SalesCustomerContactCreate
)
from sales.services import (
    CustomerSalesService, DuplicateTaxRegistrationError,
    InvalidCreditLimitError, UnsupportedCurrencyError, CustomerNotFoundError
)
from core.exceptions import ConcurrencyError

@pytest.mark.asyncio
async def test_onboard_customer_success(db_session: AsyncSession):
    # 1. Onboard a customer with address and contact
    data = CustomerCommercialOnboard(
        name="Acme Corporation",
        tax_id="US-99887766",
        primary_email="billing@acme.com",
        credit_limit=Decimal("50000.00"),
        payment_terms="Net 45",
        currency="EUR",
        notes="High-value client.",
        addresses=[
            SalesCustomerAddressCreate(
                address_type="BILLING",
                address_line1="123 Main St",
                city="San Francisco",
                postal_code="94103",
                country="US",
                is_primary=True
            )
        ],
        contacts=[
            SalesCustomerContactCreate(
                full_name="Alice Smith",
                email="alice@acme.com",
                phone="555-0199",
                role="BILLING"
            )
        ]
    )

    onboarded = await CustomerSalesService.onboard_customer(db_session, data)

    # 2. Assert core details
    assert onboarded.name == "Acme Corporation"
    assert onboarded.tax_id == "US-99887766"
    assert onboarded.primary_email == "billing@acme.com"
    assert onboarded.version_id == 1

    # 3. Assert sales commercial settings
    assert onboarded.credit_limit == Decimal("50000.00")
    assert onboarded.payment_terms == "Net 45"
    assert onboarded.currency == "EUR"
    assert onboarded.credit_hold is False

    # 4. Assert address and contacts created
    assert len(onboarded.addresses) == 1
    assert onboarded.addresses[0].address_line1 == "123 Main St"
    assert onboarded.addresses[0].city == "San Francisco"

    assert len(onboarded.contacts) == 1
    assert onboarded.contacts[0].full_name == "Alice Smith"

@pytest.mark.asyncio
async def test_onboard_customer_duplicate_tax_id(db_session: AsyncSession):
    # Create initial customer
    data1 = CustomerCommercialOnboard(
        name="Customer A",
        tax_id="TAX-DUPLICATE",
        primary_email="a@example.com"
    )
    await CustomerSalesService.onboard_customer(db_session, data1)

    # Onboard duplicate tax id customer
    data2 = CustomerCommercialOnboard(
        name="Customer B",
        tax_id="TAX-DUPLICATE",
        primary_email="b@example.com"
    )

    with pytest.raises(DuplicateTaxRegistrationError):
        await CustomerSalesService.onboard_customer(db_session, data2)

@pytest.mark.asyncio
async def test_onboard_customer_invalid_credit_limit(db_session: AsyncSession):
    data = CustomerCommercialOnboard(
        name="Negative Credit Ltd",
        credit_limit=Decimal("-10.00")
    )

    with pytest.raises(InvalidCreditLimitError):
        await CustomerSalesService.onboard_customer(db_session, data)

@pytest.mark.asyncio
async def test_update_customer_optimistic_locking(db_session: AsyncSession):
    # Onboard customer
    data = CustomerCommercialOnboard(
        name="Lock Testing Inc",
        tax_id="TAX-LOCK",
        credit_limit=Decimal("1000.00")
    )
    onboarded = await CustomerSalesService.onboard_customer(db_session, data)

    # Try updating with stale version_id
    update_data = CustomerCommercialUpdate(
        name="Updated Lock Testing Inc",
        credit_limit=Decimal("2000.00")
    )

    with pytest.raises(ConcurrencyError):
        await CustomerSalesService.update_customer(
            db_session,
            customer_id=onboarded.id,
            data=update_data,
            version_id=99  # Stale version
        )

    # Try updating with correct version_id
    updated = await CustomerSalesService.update_customer(
        db_session,
        customer_id=onboarded.id,
        data=update_data,
        version_id=onboarded.version_id
    )

    assert updated.name == "Updated Lock Testing Inc"
    assert updated.credit_limit == Decimal("2000.00")
    assert updated.version_id == 2

@pytest.mark.asyncio
async def test_credit_eligibility_checks(db_session: AsyncSession):
    # Onboard customer with $5,000 credit limit
    data = CustomerCommercialOnboard(
        name="Solvent Customer",
        credit_limit=Decimal("5000.00")
    )
    onboarded = await CustomerSalesService.onboard_customer(db_session, data)

    # Check eligibility for order of $4,000 (should pass)
    pass_eligible = await CustomerSalesService.check_credit_eligibility(
        db_session, customer_id=onboarded.id, order_amount=Decimal("4000.00")
    )
    assert pass_eligible is True

    # Check eligibility for order of $6,000 (should block and trigger hold)
    block_eligible = await CustomerSalesService.check_credit_eligibility(
        db_session, customer_id=onboarded.id, order_amount=Decimal("6000.00")
    )
    assert block_eligible is False

    # Verify hold is now active in DB
    details_stmt = select(SalesCustomerDetails).where(SalesCustomerDetails.customer_id == onboarded.id)
    res = await db_session.execute(details_stmt)
    details = res.scalars().first()
    assert details.credit_hold is True
