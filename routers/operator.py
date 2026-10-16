from fastapi import APIRouter, Depends, HTTPException, Request

from models.schemas import OperatorContentRequest, ProgramStatusRequest
from services.auth import get_current_operator, require_village_access
from services.booking import get_operator_dashboard_summary
from services.operator_assistant import PhotoRejected, save_operator_contents
from services.village_promo import publish_operator_contents
from services.supabase_client import get_village_by_id, list_contents
from services.village_programs import UnknownProgram, programs_for, set_program_operating

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


async def _content_fields(request: Request) -> tuple[str, str | None, bytes | None]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type or not content_type:
        body = OperatorContentRequest.model_validate(await request.json())
        return body.description, body.village_id, None
    form = await request.form()
    description = str(form.get("description") or "")
    other = form.get("village_id")
    other_village = str(other).strip() if other else None
    upload = form.get("photo")
    photo = None
    if hasattr(upload, "read"):
        data = await upload.read()
        if data:
            photo = data
    return description, other_village or None, photo


@router.post("/contents/publish")
async def publish_operator_content(
    request: Request,
    village_id: str | None = None,
    current_operator: dict = Depends(get_current_operator),
):
    other_village = village_id
    if "application/json" in request.headers.get("content-type", ""):
        payload = await request.json()
        if isinstance(payload, dict) and payload.get("village_id"):
            other_village = str(payload["village_id"])
    _reject_other_village(other_village, current_operator)
    return publish_operator_contents(current_operator)


@router.post("/contents")
async def create_operator_contents(
    request: Request,
    village_id: str | None = None,
    current_operator: dict = Depends(get_current_operator),
):
    description, other_village, photo = await _content_fields(request)
    _reject_other_village(other_village or village_id, current_operator)
    description = description.strip()
    if not description:
        raise HTTPException(status_code=400, detail="짧은 설명을 입력해 주세요.")
    try:
        return save_operator_contents(current_operator, description, photo)
    except PhotoRejected as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.get("/programs")
async def operator_programs(
    village_id: str | None = None,
    current_operator: dict = Depends(get_current_operator),
):
    _reject_other_village(village_id, current_operator)
    village = get_village_by_id(current_operator["village_id"]) or {}
    return {"programs": programs_for(village)}


@router.post("/programs/status")
async def update_program_status(
    body: ProgramStatusRequest,
    current_operator: dict = Depends(get_current_operator),
):
    _reject_other_village(body.village_id, current_operator)
    label = body.label.strip()
    if not label:
        raise HTTPException(status_code=400, detail="프로그램 이름을 입력해 주세요.")
    try:
        programs = set_program_operating(
            current_operator["village_id"], label, body.is_operating
        )
    except UnknownProgram as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"programs": programs}
