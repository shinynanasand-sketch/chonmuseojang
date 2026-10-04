from fastapi import APIRouter, Depends, HTTPException

from models.schemas import OperatorContentRequest
from services.auth import get_current_operator, require_village_access
from services.booking import get_operator_dashboard_summary
from services.operator_assistant import save_operator_contents
from services.supabase_client import list_contents

router = APIRouter(prefix="/api/operator", tags=["operator"])


def _reject_other_village(village_id: str | None, current_operator: dict) -> None:
    if village_id is not None:
        require_village_access(current_operator, village_id)


@router.get("/dashboard")
async def operator_dashboard(
    village_id: str | None = None,
    current_operator: dict = Depends(get_current_operator),
):
    _reject_other_village(village_id, current_operator)
    return get_operator_dashboard_summary(current_operator)


@router.get("/contents")
async def operator_contents(
    village_id: str | None = None,
    current_operator: dict = Depends(get_current_operator),
):
    _reject_other_village(village_id, current_operator)
    return {"contents": list_contents(village_id=current_operator["village_id"])}


@router.post("/contents")
async def create_operator_contents(
    body: OperatorContentRequest,
    village_id: str | None = None,
    current_operator: dict = Depends(get_current_operator),
):
    _reject_other_village(body.village_id or village_id, current_operator)
    description = body.description.strip()
    if not description:
        raise HTTPException(status_code=400, detail="짧은 설명을 입력해 주세요.")
    return save_operator_contents(current_operator, description)
