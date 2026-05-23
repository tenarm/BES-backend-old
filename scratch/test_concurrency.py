import asyncio
import os
import sys
import uuid

# Adjust path to import core package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlmodel import SQLModel, Field, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

from core.models import BESBase
from core.repository import BaseRepository
from core.exceptions import ConcurrencyError

# Define a test model inheriting from BESBase
class ConcurrencyTestProduct(BESBase, table=True):
    __tablename__ = "concurrency_test_products"
    name: str
    price: float


async def run_tests():
    # 1. Initialize SQLite in-memory database
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        
    session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    repo = BaseRepository(ConcurrencyTestProduct)
    
    # Create a test product
    async with session_maker() as session:
        product = ConcurrencyTestProduct(name="Product 1", price=100.0)
        created = await repo.create(session, product)
        product_id = created.id
        print(f"[*] Created product. ID: {product_id}, Name: '{created.name}', Version: {created.version_id}")
        assert created.version_id == 1, "Initial version should be 1"

    # --- Test Case 1: Client-side version mismatch check (repository validation) ---
    print("\n--- Test Case 1: Explicit version mismatch check ---")
    async with session_maker() as session:
        # Load object
        p1 = await repo.get(session, product_id)
        assert p1.version_id == 1
        
        # User A updates the record successfully
        print("[User A] Updating product name to 'Updated by A' with expected version 1...")
        await repo.update(session, p1, {"name": "Updated by A", "version_id": 1})
        print(f"[User A] Update success. New Version: {p1.version_id}")
        assert p1.version_id == 2
        
    async with session_maker() as session:
        # User B attempts to update the record with stale version 1
        p2 = await repo.get(session, product_id)
        assert p2.version_id == 2
        
        print("[User B] Attempting stale update (passing version_id=1)...")
        try:
            await repo.update(session, p2, {"name": "Updated by B", "version_id": 1})
            raise AssertionError("ConcurrencyError should have been raised for stale version!")
        except ConcurrencyError as e:
            print(f"[User B] Success: ConcurrencyError raised as expected: {e}")

    # --- Test Case 2: Database StaleDataError check (simultaneous session commits) ---
    print("\n--- Test Case 2: Simultaneous session commit conflict ---")
    session1 = session_maker()
    session2 = session_maker()
    try:
        # Load same record (version 2) in two separate session instances
        p_sess1 = await repo.get(session1, product_id)
        p_sess2 = await repo.get(session2, product_id)
        
        assert p_sess1.version_id == 2
        assert p_sess2.version_id == 2
        
        # Update and commit in session1 (version becomes 3 in DB)
        print("[Session 1] Updating name to 'Commit 1'...")
        await repo.update(session1, p_sess1, {"name": "Commit 1"})
        print(f"[Session 1] Success. DB version is now: {p_sess1.version_id}")
        assert p_sess1.version_id == 3
        
        # Now update and commit in session2 (still has version 2 in memory)
        print("[Session 2] Updating name to 'Commit 2' (without passing explicit version, relying on database check)...")
        try:
            await repo.update(session2, p_sess2, {"name": "Commit 2"})
            raise AssertionError("ConcurrencyError should have been raised due to StaleDataError during repo.update!")
        except ConcurrencyError as e:
            print(f"[Session 2] Success: ConcurrencyError raised as expected on commit: {e}")
            await session2.rollback()
    finally:
        await session1.close()
        await session2.close()

    # --- Test Case 3: Pessimistic locking (get_with_lock) ---
    print("\n--- Test Case 3: Pessimistic locking (FOR UPDATE) ---")
    session_lock1 = session_maker()
    session_lock2 = session_maker()
    try:
        # Acquire lock in session_lock1
        print("[Session Lock 1] Acquiring lock on product...")
        p_lock1 = await repo.get_with_lock(session_lock1, product_id)
        print("[Session Lock 1] Lock acquired.")
        
        # Attempt to acquire lock in session_lock2 with nowait=True
        print("[Session Lock 2] Attempting to acquire lock with nowait=True...")
        try:
            await repo.get_with_lock(session_lock2, product_id, nowait=True)
            if engine.dialect.name == "sqlite":
                print("[Session Lock 2] Dialect is sqlite; SELECT FOR UPDATE is a no-op, skipping lock exception check.")
            else:
                raise AssertionError("OperationalError/lock block should have occurred!")
        except OperationalError as e:
            # Dialects supporting row locks (like PostgreSQL) will raise OperationalError
            print(f"[Session Lock 2] Success: Blocked/raised exception as expected: {e}")
            await session_lock2.rollback()

            
        # Commit Session Lock 1 to release lock
        print("[Session Lock 1] Releasing lock...")
        await session_lock1.commit()
        
        # Try again in Session Lock 2, should succeed now
        print("[Session Lock 2] Attempting lock again now that lock is released...")
        p_lock2 = await repo.get_with_lock(session_lock2, product_id, nowait=True)
        print("[Session Lock 2] Success: Lock acquired successfully.")
        await session_lock2.commit()
        
    finally:
        await session_lock1.close()
        await session_lock2.close()

    print("\n[+] All concurrency control tests passed successfully!")
    await engine.dispose()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_tests())
