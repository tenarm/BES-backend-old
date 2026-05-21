"""
BES Audit & Traceability System.

Provides immutable, tamper-proof audit logging, field-level change tracking,
persistent event storage, and real-time SSE broadcasting. This is the backbone
of the BES's process transparency — feeding the frontend Timeline,
ProcessPipeline, and Activity Feed components with real data.

Design: "Fixed Envelope + Flexible JSON Payload"
- The envelope (entity_type, entity_id, action, actor) is always structured
- The payload (changes JSON) varies per action type — and that's by design
"""
import asyncio
import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Any
from sqlmodel import SQLModel, Field, select
from sqlalchemy import Column, JSON, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ─── SSE Broadcast Channel ────────────────────────────────────────────────
# In-memory pub/sub so AuditService.log_action() pushes to connected SSE clients.
# Each subscriber is an asyncio.Queue. Lightweight; scales per-process.

class _AuditBroadcaster:
    """
    In-memory fan-out broadcaster for real-time audit SSE streams.

    Fix #8: Uses a set instead of a list, and broadcast() snapshots
    subscribers before iterating — safe against concurrent subscribe/
    unsubscribe calls in the asyncio event loop. unsubscribe uses
    set.discard (idempotent, no KeyError on double-unsubscribe).
    """
    def __init__(self):
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        self._subscribers.discard(q)

    async def broadcast(self, entry_dict: dict):
        # Snapshot before iterating — prevents mutation-during-iteration
        # if a client disconnects (unsubscribe) while we are broadcasting.
        dead = []
        for q in list(self._subscribers):
            try:
                q.put_nowait(entry_dict)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers.discard(q)

audit_broadcaster = _AuditBroadcaster()

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ─── Immutable Base (Append-Only — NO soft delete, NO update) ──────────────

class ImmutableBase(SQLModel):
    """
    Base for audit/compliance tables that must be tamper-proof.
    Unlike BESBase, this has NO is_deleted, NO updated_at mutation.
    Records are write-once, read-many.
    """
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=_utc_now)
    subsidiary_id: str | None = Field(default=None, index=True)


# ─── Audit Log ─────────────────────────────────────────────────────────────

class AuditLog(ImmutableBase, table=True):
    """
    Immutable record of every business action in the BES.
    This is the single source of truth for "what happened?"
    """
    __tablename__ = "audit_log"

    # WHAT was affected
    entity_type: str = Field(index=True)      # "finance.Account", "sales.SalesOrder"
    entity_id: str = Field(index=True)         # UUID as string for flexibility
    action: str = Field(index=True)            # "CREATE", "UPDATE", "DELETE", "STATUS_CHANGE", "APPROVE", "POST"

    # WHO did it
    actor_id: Optional[str] = None             # User UUID or "system"
    actor_name: str = Field(default="system")  # Denormalized for fast display
    actor_type: str = Field(default="user")    # "user" | "system"

    # CONTEXT
    module: str = Field(index=True)            # "finance", "sales", "hr"
    correlation_id: Optional[str] = Field(default=None, index=True)  # Links to request chain
    description: str = Field(default="")       # Human-readable: "Posted journal entry JE-001"

    # WHAT changed (polymorphic JSON payload)
    changes: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)
    # Shape: { "action_data": {...}, "field_changes": [{field, old, new}], "triggered_event": "..." }

    # DOWNSTREAM effects
    event_id: Optional[str] = None             # Link to EventStore if triggered by event
    parent_audit_id: Optional[str] = None      # For causal chains (event A caused action B)


class FieldChangeLog(ImmutableBase, table=True):
    """
    Detailed before/after snapshot of individual field mutations.
    Linked to AuditLog for drill-down capability.
    """
    __tablename__ = "field_change_log"

    audit_log_id: uuid.UUID = Field(foreign_key="audit_log.id", index=True)
    entity_type: str                           # Denormalized for direct querying
    entity_id: str
    field_name: str                            # "status", "total_amount", "balance"
    old_value: Optional[str] = None            # JSON-serialized previous value
    new_value: Optional[str] = None            # JSON-serialized new value


# ─── Event Store ───────────────────────────────────────────────────────────

class EventStore(ImmutableBase, table=True):
    """
    Persistent record of every event emitted through the Event Bus.
    Enables replay, dead-letter inspection, and cross-module lineage.
    """
    __tablename__ = "event_store"

    event_type: str = Field(index=True)        # "ORDER_CONFIRMED", "INVOICE_POSTED"
    emitter_module: str                        # "sales", "finance"
    correlation_id: Optional[str] = Field(default=None, index=True)
    payload: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)

    # Processing status
    status: str = Field(default="EMITTED")     # "EMITTED", "PROCESSED", "FAILED", "DEAD_LETTER"
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    handler_count: int = Field(default=0)
    handlers_completed: int = Field(default=0)


# ─── Audit Service ─────────────────────────────────────────────────────────

class AuditService:
    """
    Central service for recording audit trail entries.
    Every mutation in the BES should flow through this service.
    """

    @staticmethod
    async def log_action(
        session: AsyncSession,
        entity_type: str,
        entity_id: str | uuid.UUID,
        action: str,
        module: str,
        description: str,
        actor_id: str | uuid.UUID | None = None,
        actor_name: str = "system",
        actor_type: str = "user",
        changes: dict | None = None,
        field_changes: list[dict] | None = None,
        correlation_id: str | None = None,
        event_id: str | None = None,
        parent_audit_id: str | None = None,
        commit: bool = False,
    ) -> AuditLog:
        """
        Records an immutable audit entry + optional field-level change log.

        Fix #7 — Transaction Contract (IMPORTANT):
            This method calls session.flush() ONLY — it does NOT commit.
            The audit entry is written to the DB write-buffer and will be
            committed atomically when the caller commits the session.
            This guarantees the audit entry and the business record land
            in the same transaction — either both succeed or both roll back.

            Pass commit=True ONLY when the audit entry is the sole operation
            in the session (e.g., a standalone system event).

        Args:
            entity_type: Dotted path like "finance.Account"
            entity_id: UUID of the affected record
            action: Verb like "CREATE", "UPDATE", "STATUS_CHANGE"
            module: Module name like "finance"
            description: Human-readable summary
            changes: Arbitrary JSON payload (the polymorphic part)
            field_changes: List of {"field", "old", "new"} dicts
            commit: If True, commits the session after flushing (default False).
        """
        from .middleware import correlation_id_context
        from .database import subsidiary_id_context
        
        cid = correlation_id or correlation_id_context.get()
        sub_id = subsidiary_id_context.get()

        log_entry = AuditLog(
            subsidiary_id=sub_id,
            entity_type=entity_type,
            entity_id=str(entity_id),
            action=action,
            actor_id=str(actor_id) if actor_id else None,
            actor_name=actor_name,
            actor_type=actor_type,
            module=module,
            correlation_id=cid,
            description=description,
            changes=changes or {},
            event_id=event_id,
            parent_audit_id=parent_audit_id,
        )
        session.add(log_entry)

        # Record field-level changes if provided
        if field_changes:
            for fc in field_changes:
                change = FieldChangeLog(
                    subsidiary_id=sub_id,
                    audit_log_id=log_entry.id,
                    entity_type=entity_type,
                    entity_id=str(entity_id),
                    field_name=fc["field"],
                    old_value=str(fc.get("old")) if fc.get("old") is not None else None,
                    new_value=str(fc.get("new")) if fc.get("new") is not None else None,
                )
                session.add(change)

        await session.flush()
        if commit:
            await session.commit()
        logger.debug(f"[Audit] {action} on {entity_type}:{entity_id} by {actor_name}")

        # Broadcast to SSE subscribers for real-time activity feed
        try:
            await audit_broadcaster.broadcast({
                "id": str(log_entry.id),
                "created_at": log_entry.created_at.isoformat(),
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                "action": action,
                "actor_name": actor_name,
                "actor_type": actor_type,
                "module": module,
                "correlation_id": cid,
                "description": description,
                "changes": changes or {},
                "event_id": event_id,
            })
        except Exception:
            pass  # SSE broadcast is best-effort, never block the main flow

        return log_entry

    @staticmethod
    async def get_entity_timeline(
        session: AsyncSession,
        entity_type: str,
        entity_id: str,
        page: int = 1,
        page_size: int = 50
    ) -> dict:
        """
        Returns the full audit timeline for a specific entity.
        This feeds the frontend Timeline component directly.
        """
        offset = (page - 1) * page_size

        # Count
        count_stmt = select(func.count()).select_from(AuditLog).where(
            AuditLog.entity_type == entity_type,
            AuditLog.entity_id == entity_id
        )
        total = (await session.execute(count_stmt)).scalar() or 0

        # Fetch entries (newest first)
        stmt = (
            select(AuditLog)
            .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await session.execute(stmt)
        entries = result.scalars().all()

        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "total": total,
            "page": page,
            "entries": entries
        }

    @staticmethod
    async def get_correlation_chain(
        session: AsyncSession,
        correlation_id: str,
    ) -> list:
        """
        Returns ALL audit entries linked by a correlation ID.
        This shows the full causal chain: request → mutation → event → downstream effect.
        """
        stmt = (
            select(AuditLog)
            .where(AuditLog.correlation_id == correlation_id)
            .order_by(AuditLog.created_at.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
