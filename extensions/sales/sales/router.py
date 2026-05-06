from fastapi import APIRouter
from .models import SalesOrder

router = APIRouter(prefix="/sales", tags=["sales"])

@router.get("/orders")
def get_orders():
    return {"status": "success", "data": []}

@router.post("/orders")
def create_order():
    return {"status": "success", "data": "Order Created"}
