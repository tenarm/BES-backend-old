import asyncio
import uuid
from decimal import Decimal
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from finance.models import Account, AccountType, PurchaseInvoice, PurchaseInvoiceLine, InvoiceStatus, JournalEntry, JournalEntryLine, JournalEntryStatus
from core.models import Vendor
import os

DATABASE_URL = "sqlite+aiosqlite:///instances/acme_corp/data/acme_corp.db"

async def seed_data():
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 1. Create AP Account if not exists
        ap_account = Account(
            id=uuid.uuid4(),
            code="2100",
            name="Accounts Payable",
            type=AccountType.LIABILITY,
            balance=Decimal("0.0")
        )
        session.add(ap_account)

        # 2. Create Expense Account
        expense_account = Account(
            id=uuid.uuid4(),
            code="5100",
            name="Office Supplies",
            type=AccountType.EXPENSE,
            balance=Decimal("0.0")
        )
        session.add(expense_account)

        # 3. Create a Vendor
        vendor = Vendor(
            id=uuid.uuid4(),
            name="Staples Inc.",
            tax_id="TAX-12345",
            primary_email="billing@staples.com",
            payment_terms="Net 30"
        )
        session.add(vendor)
        await session.flush()

        # 4. Create a Purchase Invoice
        invoice = PurchaseInvoice(
            id=uuid.uuid4(),
            vendor_id=vendor.id,
            invoice_number="INV-2024-001",
            date="2024-05-15",
            due_date="2024-06-15",
            status=InvoiceStatus.UNPAID,
            total_amount=Decimal("500.00"),
            outstanding_amount=Decimal("500.00")
        )
        session.add(invoice)
        await session.flush()

        line = PurchaseInvoiceLine(
            purchase_invoice_id=invoice.id,
            account_id=expense_account.id,
            description="Paper and Ink",
            amount=Decimal("500.00")
        )
        session.add(line)

        # 5. Create GL entry for the invoice
        je = JournalEntry(
            id=uuid.uuid4(),
            date="2024-05-15",
            reference="PI-INV-2024-001",
            description="Purchase Invoice INV-2024-001 for Vendor Staples Inc.",
            status=JournalEntryStatus.POSTED
        )
        session.add(je)
        await session.flush()

        # Debit Expense
        session.add(JournalEntryLine(
            journal_entry_id=je.id,
            account_id=expense_account.id,
            debit=Decimal("500.00"),
            credit=Decimal("0.0"),
            description="Office Supplies - Paper and Ink"
        ))
        # Credit AP
        session.add(JournalEntryLine(
            journal_entry_id=je.id,
            account_id=ap_account.id,
            debit=Decimal("0.0"),
            credit=Decimal("500.00"),
            description="Payable to Staples Inc."
        ))

        # Update balances
        expense_account.balance += Decimal("500.00")
        ap_account.balance += Decimal("500.00")

        await session.commit()
        print("Seed data created successfully!")

if __name__ == "__main__":
    asyncio.run(seed_data())
