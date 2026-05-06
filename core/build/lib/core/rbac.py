from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from .database import subsidiary_id_context

MASTER_JSON = {
    "finance": {"read": True, "write": False},
    "sales": {"read": True, "write": True}
}

class ContextAwareSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extract subsidiary_id from headers for multi-tenancy context
        subs_id = request.headers.get("X-Subsidiary-Id")
        if subs_id:
            token = subsidiary_id_context.set(subs_id)
        else:
            token = subsidiary_id_context.set(None)
            
        try:
            response = await call_next(request)
            return response
        finally:
            subsidiary_id_context.reset(token)

def get_simplified_json(user_id: str):
    # Mocking simplify logic
    return {
        "modules": ["sales", "finance"],
        "permissions": MASTER_JSON
    }
