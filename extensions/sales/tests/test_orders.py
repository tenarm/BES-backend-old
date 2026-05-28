import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Customer, Product
from sales.services import SalesOrderService
from sales.schemas import SalesOrderCreate, SalesOrderLineCreate


@pytest.mark.asyncio
async def test_sales_order_lifecycle(db_session: AsyncSession):
    # 1. Seed Customer and Product
    customer = Customer(
        name="John Doe",
        primary_email="john@doe.com",
        credit_limit=Decimal("100.0000"),
        outstanding_balance=Decimal("0.0000")
    )
    product = Product(
        name="Standard Item",
        sku="ITEM-STD",
        base_price=Decimal("10.0000")
    )
    db_session.add(customer)
    db_session.add(product)
    await db_session.commit()

    # 2. Direct Order Creation (within credit limit)
    line = SalesOrderLineCreate(
        product_id=product.id,
        qty=Decimal("5.0"),
        unit_price=Decimal("10.0000")
    )
    order_in = SalesOrderCreate(
        customer_id=customer.id,
        payment_terms="Net 30",
        line_items=[line]
    )

    order_service = SalesOrderService()
    order = await order_service.create_order(db_session, order_in)

    assert order.status == "draft"
    assert order.total_amount == Decimal("50.0000")
    assert order.credit_warning is False
    assert order.ref_number.startswith("SO-")

    # 3. Direct Order Creation (exceeding credit limit -> triggers soft warning!)
    line_exceed = SalesOrderLineCreate(
        product_id=product.id,
        qty=Decimal("15.0"),
        unit_price=Decimal("10.0000")
    )
    order_exceed_in = SalesOrderCreate(
        customer_id=customer.id,
        payment_terms="Net 30",
        line_items=[line_exceed]
    )
    order_exceed = await order_service.create_order(db_session, order_exceed_in)

    assert order_exceed.total_amount == Decimal("150.0000")
    assert order_exceed.credit_warning is True  # Soft warning!

    # 4. Confirm Order
    confirmed_order = await order_service.confirm_order(db_session, order.id)
    assert confirmed_order.status == "confirmed"

    # 5. Clone Order
    cloned = await order_service.clone_order(db_session, order.id)
    assert cloned.status == "draft"
    assert cloned.cloned_from_id == order.id
    assert cloned.total_amount == order.total_amount
