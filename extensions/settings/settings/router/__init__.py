from fastapi import APIRouter
from .company import router as company_router
from .user import router as user_router

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])
router.include_router(company_router)
router.include_router(user_router)

__all__ = ["router"]
