import uuid
import time
import logging
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from .database import subsidiary_id_context

logger = logging.getLogger(__name__)

# ─── Correlation ID Context ───────────────────────────────────────────────
# Propagated across the entire request lifecycle:
# Middleware → Services → Event Bus → Audit Log → Event Store
correlation_id_context: ContextVar[str | None] = ContextVar("correlation_id_context", default=None)

# ─── Current User Context (for audit trail) ───────────────────────────────
current_user_id_context: ContextVar[str | None] = ContextVar("current_user_id_context", default=None)
current_user_name_context: ContextVar[str | None] = ContextVar("current_user_name_context", default=None)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs every request with a unique correlation ID, method, path, and response time.
    Sets the correlation_id ContextVar for downstream propagation to
    audit logs, event bus, and field change records.
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        # Use client-provided correlation ID or generate one
        corr_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())[:12]
        token = correlation_id_context.set(corr_id)

        start_time = time.time()
        logger.info(f"[{corr_id}] → {request.method} {request.url.path}")

        try:
            response = await call_next(request)
            duration_ms = round((time.time() - start_time) * 1000, 2)
            logger.info(f"[{corr_id}] ← {response.status_code} ({duration_ms}ms)")

            response.headers["X-Correlation-ID"] = corr_id
            response.headers["X-Request-ID"] = corr_id
            return response
        finally:
            correlation_id_context.reset(token)


class ContextAwareSecurityMiddleware(BaseHTTPMiddleware):
    """
    Extracts the X-Subsidiary-Id header and injects it into
    the request-scoped ContextVar for automatic row-level filtering.
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        subs_id = request.headers.get("X-Subsidiary-Id")
        token = subsidiary_id_context.set(subs_id)
        try:
            return await call_next(request)
        finally:
            subsidiary_id_context.reset(token)
