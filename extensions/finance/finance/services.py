import uuid
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from typing import Optional, Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from core.repository import BaseRepository
from core.sequences import SequenceService
from core.events import event_bus, BaseEventPayload
from core.exceptions import EntityNotFoundError, StateTransitionError, ValidationError
from core.models.master_data import Customer
from .models import FinanceInvoice, FinanceInvoiceLine, FinancePayment
from .schemas import FinanceInvoiceCreate, FinancePaymentCreate


class InvoiceRepository(BaseRepository[FinanceInvoice]):
    def __init__(self):
        super().__init__(FinanceInvoice)


class PaymentRepository(BaseRepository[FinancePayment]):
    def __init__(self):
        super().__init__(FinancePayment)


invoice_repo = InvoiceRepository()
payment_repo = PaymentRepository()


class InvoiceService:
    def __init__(self):
        self.sequence_service = SequenceService()

    async def get_invoice(self, session: AsyncSession, invoice_id: uuid.UUID) -> Optional[FinanceInvoice]:
        return await invoice_repo.get(session, invoice_id)

    async def get_all_invoices(self, session: AsyncSession, skip: int = 0, limit: int = 100) -> Sequence[FinanceInvoice]:
        return await invoice_repo.get_all(session, skip=skip, limit=limit)

    async def create_invoice(self, session: AsyncSession, obj_in: FinanceInvoiceCreate) -> FinanceInvoice:
        ref = await self.sequence_service.next_number(session, "finance_invoice")

        subtotal = Decimal("0.0")
        tax_amount = Decimal("0.0")
        line_items = []

        for line in obj_in.line_items:
            qty = Decimal(str(line.qty))
            unit_price = Decimal(str(line.unit_price))
            discount = Decimal(str(line.discount_amount))
            tax_rate = Decimal(str(line.tax_rate))

            line_total = (qty * unit_price) - discount
            line_total = line_total.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

            line_tax = line_total * tax_rate
            line_tax = line_tax.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

            subtotal += line_total
            tax_amount += line_tax

            db_line = FinanceInvoiceLine(
                product_id=line.product_id,
                qty=qty,
                unit_price=unit_price,
                discount_amount=discount,
                tax_rate=tax_rate,
                line_total=line_total
            )
            line_items.append(db_line)

        total_amount = subtotal + tax_amount
        total_amount = total_amount.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

        invoice = FinanceInvoice(
            ref_number=ref,
            order_id=obj_in.order_id,
            customer_id=obj_in.customer_id,
            due_date=obj_in.due_date,
            status="draft",
            subtotal=subtotal,
            tax_amount=tax_amount,
            total_amount=total_amount,
            balance_due=total_amount,
            line_items=line_items
        )

        invoice = await invoice_repo.create(session, invoice)
        await session.commit()
        return invoice

    async def issue_invoice(self, session: AsyncSession, invoice_id: uuid.UUID) -> FinanceInvoice:
        invoice = await invoice_repo.get_with_lock(session, invoice_id)
        if not invoice:
            raise EntityNotFoundError("FinanceInvoice", str(invoice_id))

        if invoice.status != "draft":
            raise StateTransitionError("FinanceInvoice", invoice.status, "issued")

        invoice.status = "issued"
        session.add(invoice)

        # Update Customer Outstanding Balance (pessimistic lock)
        stmt = select(Customer).where(Customer.id == invoice.customer_id).with_for_update()
        res = await session.execute(stmt)
        customer = res.scalars().first()
        if not customer:
            raise EntityNotFoundError("Customer", str(invoice.customer_id))

        customer.outstanding_balance += invoice.total_amount
        session.add(customer)

        event_payload = BaseEventPayload(
            emitter_module="finance",
            event_type="SELL_INVOICE_GENERATED",
            data={
                "invoice_id": str(invoice.id),
                "order_id": str(invoice.order_id),
                "total_amount": str(invoice.total_amount)
            }
        )

        await session.commit()
        await event_bus.emit(event_payload)
        return invoice


class PaymentService:
    def __init__(self):
        self.sequence_service = SequenceService()

    async def get_payment(self, session: AsyncSession, payment_id: uuid.UUID) -> Optional[FinancePayment]:
        return await payment_repo.get(session, payment_id)

    async def get_all_payments(self, session: AsyncSession, skip: int = 0, limit: int = 100) -> Sequence[FinancePayment]:
        return await payment_repo.get_all(session, skip=skip, limit=limit)

    async def record_payment(self, session: AsyncSession, obj_in: FinancePaymentCreate) -> FinancePayment:
        ref = await self.sequence_service.next_number(session, "finance_payment")

        # Pessimistic lock the Invoice
        invoice = await invoice_repo.get_with_lock(session, obj_in.invoice_id)
        if not invoice:
            raise EntityNotFoundError("FinanceInvoice", str(obj_in.invoice_id))

        if invoice.status not in ("issued", "partially_paid"):
            raise ValidationError("Payment can only be recorded against issued or partially paid invoices")

        amount = Decimal(str(obj_in.amount))
        if amount > invoice.balance_due:
            raise ValidationError(f"Payment amount {amount} exceeds invoice balance due {invoice.balance_due}")

        payment = FinancePayment(
            ref_number=ref,
            invoice_id=obj_in.invoice_id,
            amount=amount,
            payment_method=obj_in.payment_method,
            payment_date=datetime.now(timezone.utc),
            status="completed"
        )
        payment = await payment_repo.create(session, payment)

        # Update Invoice balances
        invoice.balance_due -= amount
        if invoice.balance_due == Decimal("0.0"):
            invoice.status = "paid"
        else:
            invoice.status = "partially_paid"
        session.add(invoice)

        # Update Customer Outstanding Balance (pessimistic lock)
        stmt = select(Customer).where(Customer.id == invoice.customer_id).with_for_update()
        res = await session.execute(stmt)
        customer = res.scalars().first()
        if not customer:
            raise EntityNotFoundError("Customer", str(invoice.customer_id))

        customer.outstanding_balance -= amount
        session.add(customer)

        event_payload = BaseEventPayload(
            emitter_module="finance",
            event_type="SELL_PAYMENT_COLLECTED",
            data={
                "payment_id": str(payment.id),
                "invoice_id": str(payment.invoice_id),
                "amount": str(payment.amount)
            }
        )

        await session.commit()
        await event_bus.emit(event_payload)
        return payment
