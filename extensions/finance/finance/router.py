from fastapi import APIRouter
from .models import Invoice

router = APIRouter(prefix="/finance", tags=["finance"])

@router.get("/invoices")
def get_invoices():
    return {"status": "success", "data": []}
