import re
import uuid
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from .models import InventoryEntity, InventoryItemDetails, InventoryUomConversion, InventoryLot, InventoryWarehouseLocation
from .schemas import InventoryEntityCreate, ItemDetailsCreate, ItemDetailsUpdate, UomConversionCreate, LotCreate, LocationCreate, LocationUpdate
from core.models import Product, UOM
from core.events import event_bus, BaseEventPayload

logger = logging.getLogger(__name__)

SKU_REGEX = re.compile(r"^[A-Z0-9_-]{3,30}$")
CODE_REGEX = re.compile(r"^[A-Z0-9_-]{3,50}$")

# --- Custom Domain Exceptions ---

class ItemDomainException(Exception):
    """Base exception for inventory item domain errors."""
    pass

class DuplicateSkuError(ItemDomainException):
    pass

class InvalidSkuFormatError(ItemDomainException):
    pass

class CostingMethodLockedError(ItemDomainException):
    pass

class CircularUomConversionError(ItemDomainException):
    pass

class NegativeNumericValueError(ItemDomainException):
    pass

class ConcurrencyError(ItemDomainException):
    pass

class InvalidCodeFormatError(ItemDomainException):
    pass

class CircularHierarchyError(ItemDomainException):
    pass

class ActiveStockLocationError(ItemDomainException):
    pass

class NegativeCapacityError(ItemDomainException):
    pass


# --- Helper functions ---

async def _has_inventory_transactions(session: AsyncSession, product_id: uuid.UUID) -> bool:
    """
    Checks if there are stock ledger entries for the product.
    Catches errors gracefully to support staged builds where transaction tables don't exist yet.
    """
    try:
        from sqlalchemy import text
        stmt = text("SELECT COUNT(*) FROM stock_ledger_entries WHERE product_id = :prod_id AND is_deleted = 0")
        res = await session.execute(stmt, {"prod_id": str(product_id)})
        count = res.scalar() or 0
        return count > 0
    except Exception:
        # Table stock_ledger_entries does not exist in this stage yet.
        return False


async def _check_circular_conversion(session: AsyncSession, product_id: uuid.UUID, from_uom: uuid.UUID, to_uom: uuid.UUID) -> bool:
    """Verifies that adding a conversion between from_uom and to_uom does not introduce a loop."""
    if from_uom == to_uom:
        return True

    stmt = select(InventoryUomConversion).where(
        InventoryUomConversion.product_id == product_id,
        InventoryUomConversion.is_deleted == False
    )
    res = await session.execute(stmt)
    conversions = res.scalars().all()

    # Build conversion graph: from_uom -> list of to_uoms
    graph = {}
    for c in conversions:
        if c.from_uom_id not in graph:
            graph[c.from_uom_id] = []
        graph[c.from_uom_id].append(c.to_uom_id)

    # Add the proposed link
    if from_uom not in graph:
        graph[from_uom] = []
    graph[from_uom].append(to_uom)

    # DFS cycle detection
    visited = set()
    rec_stack = set()

    def has_cycle(node):
        visited.add(node)
        rec_stack.add(node)

        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                if has_cycle(neighbor):
                    return True
            elif neighbor in rec_stack:
                return True

        rec_stack.remove(node)
        return False

    # Check for cycles starting from from_uom
    return has_cycle(from_uom)


# --- Service Implementations ---

async def create_entity(session: AsyncSession, data: InventoryEntityCreate) -> InventoryEntity:
    """Preserves legacy boilerplate signature for router/entity compatibility."""
    db_obj = InventoryEntity.model_validate(data)
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


class ItemMasterService:
    
    @staticmethod
    async def list_items(
        session: AsyncSession, 
        search: Optional[str] = None, 
        subsidiary_id: Optional[str] = None,
        offset: int = 0,
        limit: int = 50
    ) -> Tuple[List[dict], int]:
        """
        Retrieves a paginated list of items with their extended details.
        """
        # Base Query joining Product and InventoryItemDetails
        stmt = (
            select(Product, InventoryItemDetails)
            .join(InventoryItemDetails, Product.id == InventoryItemDetails.product_id)
            .where(Product.is_deleted == False)
        )

        if search:
            stmt = stmt.where(
                (Product.name.ilike(f"%{search}%")) | 
                (Product.sku.ilike(f"%{search}%"))
            )
        
        if subsidiary_id:
            stmt = stmt.where(Product.subsidiary_id == subsidiary_id)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await session.execute(count_stmt)).scalar() or 0

        # Paginate results
        stmt = stmt.offset(offset).limit(limit)
        results = await session.execute(stmt)
        
        items = []
        for prod, details in results:
            item_dict = {
                "id": prod.id,
                "product_id": details.product_id,
                "name": prod.name,
                "sku": prod.sku,
                "base_price": prod.base_price,
                "uom_id": prod.uom_id,
                "subsidiary_id": prod.subsidiary_id,
                "is_deleted": prod.is_deleted,
                "version_id": details.version_id,
                "created_at": prod.created_at,
                "updated_at": prod.updated_at,
                "costing_method": details.costing_method,
                "standard_cost": details.standard_cost,
                "weighted_average_cost": details.weighted_average_cost,
                "safety_stock": details.safety_stock,
                "reorder_point": details.reorder_point,
                "is_serial_tracked": details.is_serial_tracked,
                "is_lot_tracked": details.is_lot_tracked,
                "notes": details.notes
            }
            items.append(item_dict)
            
        return items, total

    @staticmethod
    async def get_item(session: AsyncSession, product_id: uuid.UUID) -> Optional[dict]:
        """
        Fetches a single item and joins its extended inventory attributes.
        """
        stmt = (
            select(Product, InventoryItemDetails)
            .join(InventoryItemDetails, Product.id == InventoryItemDetails.product_id)
            .where(Product.id == product_id, Product.is_deleted == False)
        )
        res = await session.execute(stmt)
        row = res.first()
        if not row:
            return None
            
        prod, details = row
        return {
            "id": prod.id,
            "product_id": details.product_id,
            "name": prod.name,
            "sku": prod.sku,
            "base_price": prod.base_price,
            "uom_id": prod.uom_id,
            "subsidiary_id": prod.subsidiary_id,
            "is_deleted": prod.is_deleted,
            "version_id": details.version_id,
            "created_at": prod.created_at,
            "updated_at": prod.updated_at,
            "costing_method": details.costing_method,
            "standard_cost": details.standard_cost,
            "weighted_average_cost": details.weighted_average_cost,
            "safety_stock": details.safety_stock,
            "reorder_point": details.reorder_point,
            "is_serial_tracked": details.is_serial_tracked,
            "is_lot_tracked": details.is_lot_tracked,
            "notes": details.notes
        }

    @staticmethod
    async def onboard_item(session: AsyncSession, data: ItemDetailsCreate) -> dict:
        """
        Creates a new product in core and links its inventory details extension.
        """
        # Validate SKU format
        if not SKU_REGEX.match(data.sku):
            raise InvalidSkuFormatError(f"SKU '{data.sku}' contains invalid characters or does not fit size limits (3-30 chars).")

        # Validate unique SKU
        stmt = select(Product).where(Product.sku == data.sku, Product.is_deleted == False)
        existing = (await session.execute(stmt)).scalars().first()
        if existing:
            raise DuplicateSkuError(f"SKU '{data.sku}' already exists in catalog.")

        # Validate non-negative numbers
        if data.base_price < 0 or data.standard_cost < 0 or data.weighted_average_cost < 0 or data.safety_stock < 0 or data.reorder_point < 0:
            raise NegativeNumericValueError("Standard costs, prices, safety stock, and reorder levels must be positive values.")

        # Verify UOM exists
        uom_stmt = select(UOM).where(UOM.id == data.uom_id)
        uom_record = (await session.execute(uom_stmt)).scalars().first()
        if not uom_record:
            raise ItemDomainException("Assigned Base UOM is not registered in the system.")

        # Create core product
        product = Product(
            name=data.name,
            sku=data.sku,
            base_price=data.base_price,
            uom_id=data.uom_id,
            subsidiary_id=data.subsidiary_id
        )
        session.add(product)
        await session.flush() # Secure product ID

        # Create inventory extension
        details = InventoryItemDetails(
            product_id=product.id,
            costing_method=data.costing_method.upper(),
            standard_cost=data.standard_cost,
            weighted_average_cost=data.weighted_average_cost,
            safety_stock=data.safety_stock,
            reorder_point=data.reorder_point,
            is_serial_tracked=data.is_serial_tracked,
            is_lot_tracked=data.is_lot_tracked,
            notes=data.notes
        )
        session.add(details)
        await session.commit()
        await session.refresh(product)
        await session.refresh(details)

        # Emit pub/sub event post-commit
        try:
            payload = BaseEventPayload(
                emitter_module="inventory",
                event_type="ITEM_MASTER_CREATED",
                data={
                    "product_id": str(product.id),
                    "sku": product.sku,
                    "name": product.name,
                    "costing_method": details.costing_method
                }
            )
            await event_bus.emit(payload)
        except Exception as e:
            logger.error(f"Failed to emit ITEM_MASTER_CREATED event: {e}")

        return {
            "id": product.id,
            "product_id": details.product_id,
            "name": product.name,
            "sku": product.sku,
            "base_price": product.base_price,
            "uom_id": product.uom_id,
            "subsidiary_id": product.subsidiary_id,
            "is_deleted": product.is_deleted,
            "version_id": details.version_id,
            "created_at": product.created_at,
            "updated_at": product.updated_at,
            "costing_method": details.costing_method,
            "standard_cost": details.standard_cost,
            "weighted_average_cost": details.weighted_average_cost,
            "safety_stock": details.safety_stock,
            "reorder_point": details.reorder_point,
            "is_serial_tracked": details.is_serial_tracked,
            "is_lot_tracked": details.is_lot_tracked,
            "notes": details.notes
        }

    @staticmethod
    async def update_item(session: AsyncSession, product_id: uuid.UUID, data: ItemDetailsUpdate, expected_version: int) -> dict:
        """
        Updates item variables, enforcing immutability and optimistic concurrency locking.
        """
        # Fetch records
        prod_stmt = select(Product).where(Product.id == product_id, Product.is_deleted == False)
        product = (await session.execute(prod_stmt)).scalars().first()
        if not product:
            raise ItemDomainException("Item does not exist.")

        details_stmt = select(InventoryItemDetails).where(InventoryItemDetails.product_id == product_id)
        details = (await session.execute(details_stmt)).scalars().first()
        if not details:
            raise ItemDomainException("Inventory details extension not found.")

        # Optimistic Locking check
        if details.version_id != expected_version:
            raise ConcurrencyError("The record was modified by another user. Please reload and try again.")

        events_to_emit = []

        # Enforce costing method immutability check if transactions exist
        if data.costing_method and data.costing_method != details.costing_method:
            if await _has_inventory_transactions(session, product_id):
                raise CostingMethodLockedError("Cannot alter costing method after stock transactions have been posted.")
            details.costing_method = data.costing_method.upper()

        # Update core Product fields
        if data.name is not None:
            product.name = data.name
        if data.base_price is not None:
            if data.base_price < 0:
                raise NegativeNumericValueError("Base price cannot be negative.")
            product.base_price = data.base_price
        if data.uom_id is not None:
            if await _has_inventory_transactions(session, product_id):
                raise ItemDomainException("Cannot change base UOM after inventory transactions have been posted.")
            product.uom_id = data.uom_id
        if data.subsidiary_id is not None:
            product.subsidiary_id = data.subsidiary_id

        # Update inventory-specific details
        if data.standard_cost is not None:
            if data.standard_cost < 0:
                raise NegativeNumericValueError("Standard cost cannot be negative.")
            old_cost = details.standard_cost
            details.standard_cost = data.standard_cost
            if old_cost != data.standard_cost:
                payload = BaseEventPayload(
                    emitter_module="inventory",
                    event_type="ITEM_COST_MODIFIED",
                    data={
                        "product_id": str(product.id),
                        "sku": product.sku,
                        "old_cost": str(old_cost),
                        "new_cost": str(data.standard_cost)
                    }
                )
                events_to_emit.append(payload)

        if data.weighted_average_cost is not None:
            if data.weighted_average_cost < 0:
                raise NegativeNumericValueError("Weighted average cost cannot be negative.")
            details.weighted_average_cost = data.weighted_average_cost

        if data.safety_stock is not None:
            if data.safety_stock < 0:
                raise NegativeNumericValueError("Safety stock cannot be negative.")
            details.safety_stock = data.safety_stock

        if data.reorder_point is not None:
            if data.reorder_point < 0:
                raise NegativeNumericValueError("Reorder level point cannot be negative.")
            details.reorder_point = data.reorder_point

        if data.is_serial_tracked is not None:
            details.is_serial_tracked = data.is_serial_tracked
        if data.is_lot_tracked is not None:
            details.is_lot_tracked = data.is_lot_tracked
        if data.notes is not None:
            details.notes = data.notes

        # Increment version automatically for optimistic concurrency control
        details.version_id += 1

        session.add(product)
        session.add(details)
        await session.commit()
        
        await session.refresh(product)
        await session.refresh(details)

        # Post-Commit Event Dispatching
        for payload in events_to_emit:
            try:
                await event_bus.emit(payload)
            except Exception as e:
                logger.error(f"Failed to emit event {payload.event_type}: {e}")

        return {
            "id": product.id,
            "product_id": details.product_id,
            "name": product.name,
            "sku": product.sku,
            "base_price": product.base_price,
            "uom_id": product.uom_id,
            "subsidiary_id": product.subsidiary_id,
            "is_deleted": product.is_deleted,
            "version_id": details.version_id,
            "created_at": product.created_at,
            "updated_at": product.updated_at,
            "costing_method": details.costing_method,
            "standard_cost": details.standard_cost,
            "weighted_average_cost": details.weighted_average_cost,
            "safety_stock": details.safety_stock,
            "reorder_point": details.reorder_point,
            "is_serial_tracked": details.is_serial_tracked,
            "is_lot_tracked": details.is_lot_tracked,
            "notes": details.notes
        }

    @staticmethod
    async def add_uom_conversion(session: AsyncSession, product_id: uuid.UUID, data: UomConversionCreate) -> InventoryUomConversion:
        """
        Registers a new unit of measure conversion multiplier after checking for circular loops.
        """
        # Validate positive scale multiplier
        if data.multiplier <= 0:
            raise NegativeNumericValueError("UOM conversion multipliers must be greater than zero.")

        # Check for circular conversion paths
        if await _check_circular_conversion(session, product_id, data.from_uom_id, data.to_uom_id):
            raise CircularUomConversionError("Circular UOM conversion loops are not allowed.")

        conversion = InventoryUomConversion(
            product_id=product_id,
            from_uom_id=data.from_uom_id,
            to_uom_id=data.to_uom_id,
            multiplier=data.multiplier
        )
        session.add(conversion)
        await session.commit()
        await session.refresh(conversion)
        return conversion

    @staticmethod
    async def list_conversions(session: AsyncSession, product_id: uuid.UUID) -> List[InventoryUomConversion]:
        """Lists active UOM conversions for a specific item."""
        stmt = select(InventoryUomConversion).where(
            InventoryUomConversion.product_id == product_id,
            InventoryUomConversion.is_deleted == False
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def recalculate_weighted_average_cost(
        session: AsyncSession, 
        product_id: uuid.UUID, 
        received_qty: Decimal, 
        received_price: Decimal,
        current_stock: Decimal
    ) -> Decimal:
        """
        Recalculates the Weighted Average Cost (WAC) using pessimistic row-level locking.
        """
        if received_qty <= 0 or received_price < 0:
            raise ItemDomainException("Received quantity must be positive and price cannot be negative.")

        # Secure record with FOR UPDATE pessimistic lock
        stmt = (
            select(InventoryItemDetails)
            .where(InventoryItemDetails.product_id == product_id)
            .with_for_update()
        )
        res = await session.execute(stmt)
        details = res.scalar_one_or_none()
        if not details:
            raise ItemDomainException("Item details extension not found.")

        # Costing Formulation:
        # C_new = ((Q_current * C_current) + (Q_received * P_received)) / (Q_current + Q_received)
        current_cost = details.weighted_average_cost
        
        total_current_value = current_stock * current_cost
        total_received_value = received_qty * received_price
        total_qty = current_stock + received_qty
        
        if total_qty <= 0:
            new_cost = Decimal("0.0")
        else:
            new_cost = (total_current_value + total_received_value) / total_qty
            
        # Quantize to 4 decimals (rounding standard)
        final_cost = new_cost.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        
        details.weighted_average_cost = final_cost
        session.add(details)
        await session.commit()
        await session.refresh(details)
        
        return final_cost


class InventoryLotService:
    
    @staticmethod
    async def create_lot(session: AsyncSession, product_id: uuid.UUID, data: LotCreate) -> InventoryLot:
        """Creates a batch lot record."""
        # Ensure unique lot number for this product
        stmt = select(InventoryLot).where(
            InventoryLot.product_id == product_id,
            InventoryLot.lot_number == data.lot_number,
            InventoryLot.is_deleted == False
        )
        existing = (await session.execute(stmt)).scalars().first()
        if existing:
            raise ItemDomainException(f"Lot number '{data.lot_number}' is already registered for this item.")

        lot = InventoryLot(
            product_id=product_id,
            lot_number=data.lot_number,
            manufacturing_date=data.manufacturing_date,
            expiry_date=data.expiry_date
        )
        session.add(lot)
        await session.commit()
        await session.refresh(lot)
        return lot

    @staticmethod
    async def list_lots(session: AsyncSession, product_id: uuid.UUID) -> List[InventoryLot]:
        """Lists active lots for a product."""
        stmt = select(InventoryLot).where(
            InventoryLot.product_id == product_id,
            InventoryLot.is_deleted == False
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())


# --- Warehouse Location Helpers ---

async def _has_stock_balance(session: AsyncSession, location_id: uuid.UUID) -> bool:
    """Checks if there is active inventory stock inside the location."""
    try:
        from sqlalchemy import text
        stmt = text("SELECT SUM(quantity) FROM stock_balances WHERE location_id = :loc_id AND is_deleted = 0")
        res = await session.execute(stmt, {"loc_id": str(location_id)})
        qty = res.scalar() or Decimal("0")
        return qty > 0
    except Exception:
        return False


async def _check_circular_parent(session: AsyncSession, start_id: uuid.UUID, parent_id: uuid.UUID) -> bool:
    """Verifies if parenting start_id to parent_id creates a loop."""
    current_parent = parent_id
    visited = set()
    while current_parent is not None:
        if current_parent == start_id:
            return True
        if current_parent in visited:
            break
        visited.add(current_parent)
        
        stmt = select(InventoryWarehouseLocation.parent_id).where(
            InventoryWarehouseLocation.id == current_parent,
            InventoryWarehouseLocation.is_deleted == False
        )
        res = await session.execute(stmt)
        current_parent = res.scalar()
        
    return False


# --- Warehouse Location Service ---

class WarehouseLocationService:
    
    @staticmethod
    async def create_location(session: AsyncSession, data: LocationCreate) -> InventoryWarehouseLocation:
        """Onboards a physical warehouse or shelving coordinates."""
        code_upper = data.code.strip().upper()
        if not CODE_REGEX.match(code_upper):
            raise InvalidCodeFormatError(f"Location code '{data.code}' is invalid. Use 3-50 alphanumeric characters.")

        stmt = select(InventoryWarehouseLocation).where(
            InventoryWarehouseLocation.code == code_upper,
            InventoryWarehouseLocation.is_deleted == False
        )
        existing = (await session.execute(stmt)).scalars().first()
        if existing:
            raise ItemDomainException(f"Location code '{code_upper}' is already registered.")

        if data.max_volume < Decimal("0.0") or data.max_weight < Decimal("0.0"):
            raise NegativeCapacityError("Capacity volume and weight limits must be positive values.")

        if data.parent_id:
            parent_stmt = select(InventoryWarehouseLocation).where(
                InventoryWarehouseLocation.id == data.parent_id,
                InventoryWarehouseLocation.is_deleted == False
            )
            parent = (await session.execute(parent_stmt)).scalars().first()
            if not parent:
                raise ItemDomainException(f"Parent location UUID '{data.parent_id}' not found.")

        location = InventoryWarehouseLocation(
            code=code_upper,
            name=data.name,
            type=data.type,
            parent_id=data.parent_id,
            address=data.address,
            contact_name=data.contact_name,
            contact_phone=data.contact_phone,
            max_volume=data.max_volume,
            max_weight=data.max_weight,
            restricted_item_categories=data.restricted_item_categories
        )
        session.add(location)
        await session.commit()
        await session.refresh(location)

        try:
            payload = BaseEventPayload(
                emitter_module="inventory",
                event_type="WAREHOUSE_LOCATION_CREATED",
                data={
                    "location_id": str(location.id),
                    "code": location.code,
                    "name": location.name,
                    "type": location.type
                }
            )
            await event_bus.emit(payload)
        except Exception as e:
            logger.error(f"Failed to emit WAREHOUSE_LOCATION_CREATED: {e}")

        return location

    @staticmethod
    async def update_location(
        session: AsyncSession, 
        id: uuid.UUID, 
        data: LocationUpdate, 
        version_id: int
    ) -> InventoryWarehouseLocation:
        """Modifies location settings with concurrency & loop prevention checks."""
        stmt = select(InventoryWarehouseLocation).where(
            InventoryWarehouseLocation.id == id,
            InventoryWarehouseLocation.is_deleted == False
        ).with_for_update()
        result = await session.execute(stmt)
        location = result.scalars().first()
        if not location:
            raise ItemDomainException("Location not found.")

        if location.version_id != version_id:
            raise ConcurrencyError("Concurrency Conflict: Location record has been modified by another process.")

        if data.max_volume is not None and data.max_volume < Decimal("0.0"):
            raise NegativeCapacityError("Max volume capacity limit cannot be negative.")
        if data.max_weight is not None and data.max_weight < Decimal("0.0"):
            raise NegativeCapacityError("Max weight capacity limit cannot be negative.")

        if data.is_active is False and location.is_active:
            stock_check = await _has_stock_balance(session, id)
            if stock_check:
                raise ActiveStockLocationError("Cannot deactivate location because it contains active inventory.")

        if data.parent_id is not None and data.parent_id != location.parent_id:
            if data.parent_id == id:
                raise CircularHierarchyError("A location cannot be its own parent.")
            
            is_circular = await _check_circular_parent(session, id, data.parent_id)
            if is_circular:
                raise CircularHierarchyError("Hierarchy cycle detected: proposed parent is a descendant of this location.")

        if data.name is not None:
            location.name = data.name
        if data.type is not None:
            location.type = data.type
        if data.parent_id is not None:
            location.parent_id = data.parent_id
        if data.address is not None:
            location.address = data.address
        if data.contact_name is not None:
            location.contact_name = data.contact_name
        if data.contact_phone is not None:
            location.contact_phone = data.contact_phone
        if data.max_volume is not None:
            location.max_volume = data.max_volume
        if data.max_weight is not None:
            location.max_weight = data.max_weight
        if data.is_active is not None:
            location.is_active = data.is_active
        if data.audit_locked is not None:
            location.audit_locked = data.audit_locked
        if data.restricted_item_categories is not None:
            location.restricted_item_categories = data.restricted_item_categories

        location.version_id += 1
        session.add(location)
        await session.commit()
        await session.refresh(location)

        try:
            payload = BaseEventPayload(
                emitter_module="inventory",
                event_type="WAREHOUSE_LOCATION_UPDATED",
                data={
                    "location_id": str(location.id),
                    "code": location.code,
                    "is_active": location.is_active,
                    "audit_locked": location.audit_locked
                }
            )
            await event_bus.emit(payload)
        except Exception as e:
            logger.error(f"Failed to emit WAREHOUSE_LOCATION_UPDATED: {e}")

        return location
