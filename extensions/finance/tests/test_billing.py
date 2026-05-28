import pytest
from decimal import Decimal
import uuid
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Customer, Product
from finance.services import InvoiceService, PaymentService
from finance.schemas import FinanceInvoiceCreate, FinanceInvoiceLineCreate, FinancePaymentCreate


@pytest.mark.asyncio
async def test_billing_invoice_and_payment_lifecycle(db_session: AsyncSession):
    # 1. Seed Customer and Product
    customer = Customer(
        name="Precise Test Customer",
        primary_email="precise@test.com",
        credit_limit=Decimal("500.0000"),
        outstanding_balance=Decimal("0.0000")
    )
    product = Product(
        name="Billed Product",
        sku="TEST-SKU-BILL",
        base_price=Decimal("20.0000")
    )
    db_session.add(customer)
    db_session.add(product)
    await db_session.commit()

    # 2. Create Invoice
    # Expected line_total = 10 * 20 = 200.0000
    # Expected line_tax = 200.0000 * 0.10 = 20.0000
    # Expected total_amount = 220.0000
    line = FinanceInvoiceLineCreate(
        product_id=product.id,
        qty=Decimal("10.0"),
        unit_price=Decimal("20.0000"),
        tax_rate=Decimal("0.10")
    )

    invoice_in = FinanceInvoiceCreate(
        order_id=uuid.uuid4(),
        customer_id=customer.id,
        due_date=date.today(),
        line_items=[line]
    )

    invoice_service = InvoiceService()
    invoice = await invoice_service.create_invoice(db_session, invoice_in)

    assert invoice.status == "draft"
    assert invoice.total_amount == Decimal("220.0000")
    assert invoice.balance_due == Decimal("220.0000")

    # 3. Issue Invoice -> Outstanding balance increases!
    issued = await invoice_service.issue_invoice(db_session, invoice.id)
    assert issued.status == "issued"

    await db_session.refresh(customer)
    assert customer.outstanding_balance == Decimal("220.0000")

    # 4. Record Payment -> Outstanding balance decreases!
    payment_service = PaymentService()
    payment_in = FinancePaymentCreate(
        invoice_id=invoice.id,
        amount=Decimal("220.0000"),
        payment_method="bank_transfer"
    )
    payment = await payment_service.record_payment(db_session, payment_in)

    assert payment.status == "completed"
    assert payment.amount == Decimal("220.0000")

    await db_session.refresh(issued)
    await db_session.refresh(customer)

    assert issued.status == "paid"
    assert issued.balance_due == Decimal("0.0000")
    assert customer.outstanding_balance == Decimal("0.0000")
