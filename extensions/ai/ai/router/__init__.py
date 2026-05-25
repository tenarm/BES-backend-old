from fastapi import APIRouter
from .entity import router as entity_router

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])
router.include_router(entity_router)

__all__ = ["router"]
