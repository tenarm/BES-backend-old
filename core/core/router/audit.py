"""
Audit & Observability Router
============================
Exposes read-only endpoints for audit timelines, causal chains, process workflow
definitions, and a Server-Sent Events stream for real-time activity monitoring.

Note: intentionally separate from the auth router.
  - auth router  → identity concerns (login, refresh, revoke, /me)
  - audit router → observability concerns (timelines, chains, SSE)
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_async_session
from ..models import User
from ..auth import get_current_user

logger = logging.getLogger(__name__)

audit_router = APIRouter(prefix="/api/v1/audit", tags=["Audit & Observability"])


# --- Audit Timeline Endpoints (on audit_router, not auth router) ---
@audit_router.get("/{entity_type}/{entity_id}")
async def get_entity_audit_timeline(
    entity_type: str,
    entity_id: str,
    page: int = 1,
    page_size: int = 50,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Returns the full audit timeline for a specific entity. Feeds the frontend Timeline."""
    from ..audit import AuditService
    timeline = await AuditService.get_entity_timeline(session, entity_type, entity_id, page, page_size)
    return {"status": "success", "data": timeline}


@audit_router.get("/chain/{correlation_id}")
async def get_correlation_chain(
    correlation_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """Returns all audit entries linked by a correlation ID (full causal chain)."""
    from ..audit import AuditService
    chain = await AuditService.get_correlation_chain(session, correlation_id)
    return {"status": "success", "data": chain}


@audit_router.get("/processes", response_model=dict)
async def get_processes(
    module: str | None = None,
    user: User = Depends(get_current_user)
):
    """
    Returns process workflow schema definitions.
    Can be optionally filtered by module (e.g., ?module=finance).
    Definitions are dynamically filtered and resolved based on client licenses.
    """
    from ..processes import PROCESS_DEFINITIONS, resolve_process_for_client
    
    # Resolve definitions for the active client context
    resolved_defs = {
        pid: resolve_process_for_client(pdef)
        for pid, pdef in PROCESS_DEFINITIONS.items()
    }
    
    if module:
        module_procs = {
            pid: pdef for pid, pdef in resolved_defs.items()
            if pdef.get("module") == module
        }
        return {"status": "success", "data": module_procs}
    return {"status": "success", "data": resolved_defs}


@audit_router.get("/processes/{process_id}", response_model=dict)
async def get_process_definition(
    process_id: str,
    user: User = Depends(get_current_user)
):
    """Returns the process workflow schema definition for the given process_id."""
    from ..processes import PROCESS_DEFINITIONS, resolve_process_for_client
    definition = PROCESS_DEFINITIONS.get(process_id)
    if not definition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Process definition for '{process_id}' not found."
        )
    return {"status": "success", "data": resolve_process_for_client(definition)}


# --- SSE: Real-Time Activity Stream (on audit_router) ---
@audit_router.get("/stream")
async def audit_sse_stream(
    module: str | None = None,
    entity_type: str | None = None,
    user: User = Depends(get_current_user),
):
    """
    Server-Sent Events stream for real-time audit activity.
    The frontend connects once and receives live audit entries as they happen.

    Optional filters:
      ?module=finance     — only finance module events
      ?entity_type=finance.JournalEntry — only journal entry events

    Usage (frontend):
      const es = new EventSource('/api/v1/auth/audit/stream?module=finance');
      es.onmessage = (e) => { const entry = JSON.parse(e.data); ... };
    """
    import asyncio
    import json
    from starlette.responses import StreamingResponse
    from ..audit import audit_broadcaster

    queue = audit_broadcaster.subscribe()

    async def event_generator():
        try:
            # Send initial keepalive
            yield f"event: connected\ndata: {json.dumps({'status': 'connected', 'user': user.username})}\n\n"

            while True:
                try:
                    entry = await asyncio.wait_for(queue.get(), timeout=30.0)
                    # Apply filters
                    if module and entry.get("module") != module:
                        continue
                    if entity_type and entry.get("entity_type") != entity_type:
                        continue
                    yield f"data: {json.dumps(entry, default=str)}\n\n"
                except asyncio.TimeoutError:
                    # Keepalive to prevent connection timeout
                    yield f": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            audit_broadcaster.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )
