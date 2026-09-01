from fastapi import APIRouter, Depends

from services.auth import get_current_operator
from services.booking import get_operator_dashboard_summary

router = APIRouter(prefix="/api/operator", tags=["operator"])


@router.get("/dashboard")
async def operator_dashboard(current_operator: dict = Depends(get_current_operator)):
    return get_operator_dashboard_summary(current_operator)
