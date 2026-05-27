import pytest
import uuid
from decimal import Decimal
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Vendor
from supply_chain.models import SupplierDetails, SupplierAddress, SupplierContact
from supply_chain.schemas import (
    SupplierOnboard, SupplierUpdate,
    SupplierAddressCreate, SupplierContactCreate
)
from supply_chain.services import (
    SupplierService, DuplicateTaxRegistrationError,
    InvalidLeadTimeDaysError, InvalidTargetScoreError, SupplierNotFoundError
)
from core.exceptions import ConcurrencyError

@pytest.mark.asyncio
async def test_onboard_supplier_success(db_session: AsyncSession):
    # 1. Onboard a supplier with address and contact
    data = SupplierOnboard(
        name="Global Sourcing Corp",
        tax_id="US-99112233",
        primary_email="billing@globalsourcing.com",
        payment_terms="Net 30",
        currency="EUR",
        lead_time_days=5,
        otif_target=Decimal("98.0000"),
        notes="Strategic manufacturing partner.",
        addresses=[
            SupplierAddressCreate(
                address_type="BILLING_REMIT",
                address_line1="456 Industrial Pkwy",
                city="Chicago",
                postal_code="60609",
                country="US",
                is_primary=True
            )
        ],
        contacts=[
            SupplierContactCreate(
                full_name="Bob Miller",
                email="bob@globalsourcing.com",
                phone="555-0122",
                role="SOURCING",
                is_primary=True
            )
        ]
    )

    onboarded = await SupplierService.onboard_supplier(db_session, data)

    # 2. Assert core details
    assert onboarded.name == "Global Sourcing Corp"
    assert onboarded.tax_id == "US-99112233"
    assert onboarded.primary_email == "billing@globalsourcing.com"
    assert onboarded.payment_terms == "Net 30"
    assert onboarded.version_id == 1

    # 3. Assert extended logistics settings
    assert onboarded.currency == "EUR"
    assert onboarded.lead_time_days == 5
    assert onboarded.otif_target == Decimal("98.0000")
    assert onboarded.otif_score == Decimal("100.0000")
    assert onboarded.purchasing_hold is False

    # 4. Assert address and contacts created
    assert len(onboarded.addresses) == 1
    assert onboarded.addresses[0].address_line1 == "456 Industrial Pkwy"
    assert onboarded.addresses[0].city == "Chicago"

    assert len(onboarded.contacts) == 1
    assert onboarded.contacts[0].full_name == "Bob Miller"

@pytest.mark.asyncio
async def test_onboard_supplier_duplicate_tax_id(db_session: AsyncSession):
    # Create initial supplier
    data1 = SupplierOnboard(
        name="Vendor A",
        tax_id="TAX-SUPP-DUP",
        primary_email="a@example.com"
    )
    await SupplierService.onboard_supplier(db_session, data1)

    # Onboard duplicate tax id supplier
    data2 = SupplierOnboard(
        name="Vendor B",
        tax_id="TAX-SUPP-DUP",
        primary_email="b@example.com"
    )

    with pytest.raises(DuplicateTaxRegistrationError):
        await SupplierService.onboard_supplier(db_session, data2)

@pytest.mark.asyncio
async def test_onboard_supplier_invalid_lead_time(db_session: AsyncSession):
    data = SupplierOnboard(
        name="Negative Lead Time Ltd",
        lead_time_days=-3
    )

    with pytest.raises(InvalidLeadTimeDaysError):
        await SupplierService.onboard_supplier(db_session, data)

@pytest.mark.asyncio
async def test_update_supplier_optimistic_locking(db_session: AsyncSession):
    # Onboard supplier
    data = SupplierOnboard(
        name="Lock Test Vendor",
        tax_id="TAX-SUPP-LOCK",
        lead_time_days=4
    )
    onboarded = await SupplierService.onboard_supplier(db_session, data)

    # Try updating with stale version_id
    update_data = SupplierUpdate(
        name="Updated Lock Test Vendor",
        lead_time_days=6
    )

    with pytest.raises(ConcurrencyError):
        await SupplierService.update_supplier(
            db_session,
            vendor_id=onboarded.id,
            data=update_data,
            version_id=99  # Stale version
        )

    # Try updating with correct version_id
    updated = await SupplierService.update_supplier(
        db_session,
        vendor_id=onboarded.id,
        data=update_data,
        version_id=onboarded.version_id
    )

    assert updated.name == "Updated Lock Test Vendor"
    assert updated.lead_time_days == 6
    assert updated.version_id == 2

@pytest.mark.asyncio
async def test_evaluate_performance_metrics(db_session: AsyncSession):
    # Onboard supplier
    data = SupplierOnboard(
        name="Performance Vendor",
        tax_id="TAX-PERF-CHECK",
        otif_target=Decimal("95.0000")
    )
    onboarded = await SupplierService.onboard_supplier(db_session, data)

    # Evaluate metrics (should evaluate using mocks / fallback)
    evaluated = await SupplierService.evaluate_performance_metrics(db_session, vendor_id=onboarded.id)
    
    assert evaluated.otif_score == Decimal("90.0000")  # Matches our fallback mock logic in services
    assert evaluated.defect_rate == Decimal("1.2500")  # Matches our fallback mock logic in services
