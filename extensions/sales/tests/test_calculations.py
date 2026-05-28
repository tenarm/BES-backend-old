import pytest
from decimal import Decimal
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Customer, Product
from sales.services import QuotationService
from sales.schemas import SalesQuotationCreate, SalesQuotationLineCreate


@pytest.mark.asyncio
async def test_financial_calculations_precision(db_session: AsyncSession):
    # 1. Seed Customer and Product
    customer = Customer(
        name="Apex Test Customer",
        primary_email="apex@test.com",
        credit_limit=Decimal("50000.0000"),
        outstanding_balance=Decimal("0.0000")
    )
    product = Product(
        name="Precise Test Product",
        sku="TEST-SKU-PREC",
        base_price=Decimal("10.1234")
    )
    db_session.add(customer)
    db_session.add(product)
    await db_session.commit()

    # 2. Quotation parameters
    # Line 1: qty = 3, unit_price = 10.1234, discount = 0.50, tax_rate = 0.15
    # Expected line total = (3 * 10.1234) - 0.50 = 30.3702 - 0.50 = 29.8702
    # Expected line tax = 29.8702 * 0.15 = 4.48053 -> quantize to 4.4805
    # Expected total = 29.8702 + 4.4805 = 34.3507
    line = SalesQuotationLineCreate(
        product_id=product.id,
        qty=Decimal("3.0"),
        unit_price=Decimal("10.1234"),
        discount_amount=Decimal("0.50"),
        tax_rate=Decimal("0.15")
    )

    quote_in = SalesQuotationCreate(
        customer_id=customer.id,
        valid_until=date.today() + timedelta(days=30),
        line_items=[line]
    )

    quote_service = QuotationService()
    quote = await quote_service.create_quotation(db_session, quote_in)

    assert quote.subtotal == Decimal("29.8702")
    assert quote.tax_amount == Decimal("4.4805")
    assert quote.total_amount == Decimal("34.3507")
