from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import HTMLResponse

from config import CRON_SECRET
from models.schemas import RecommendRequest
from services.booking import get_public_dashboard_summary
from services.public_data_sync import sync_village_data
from services.recommend import recommend_villages
from services.supabase_client import list_program_status_map, list_public_villages
from services.tourapi import get_nearby_for_village
from services.dev_admin import clear_village_records, dev_open, issue_dev_cookie, village_choices
from services.guide_access import codes_open, guide_rows, issue_unlock_cookie
from services.calendar_board import (
    calendar_snapshot,
    delete_calendar_from_token,
    save_calendar_from_token,
    set_booking_status_from_token,
)
from services.kakao_home import home_kakao_guide
from services.village_promo import list_published_villages, public_village_promo
from services.village_programs import programs_for
from services.trust_score import calculate_trust_score

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return request.app.state.templates.TemplateResponse(
        request,
        "index.html",
        {"title": "체험마을 AI사무장", "kakao_guide": home_kakao_guide()},
    )


@router.get("/recommend", response_class=HTMLResponse)
async def recommend_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request, "recommend.html", {"title": "AI 추천"}
    )


@router.get("/map", response_class=HTMLResponse)
async def map_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request, "map.html", {"title": "마을 지도"}
    )


@router.get("/nearby", response_class=HTMLResponse)
async def nearby_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request, "nearby.html", {"title": "주변정보"}
    )


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request, "dashboard.html", {"title": "운영 현황"}
    )


@router.get("/villages", response_class=HTMLResponse)
async def villages_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request,
        "villages.html",
        {"title": "마을 소개", "villages": list_published_villages()},
    )


@router.get("/village/{village_id}", response_class=HTMLResponse)
async def village_page(request: Request, village_id: str):
    promo = public_village_promo(village_id)
    if promo is None:
        raise HTTPException(status_code=404, detail="마을을 찾지 못했습니다.")
    return request.app.state.templates.TemplateResponse(
        request, "village.html", {"title": promo["village_name"] or "마을", "promo": promo}
    )


def _calendar_result(result: dict):
    if result.get("ok"):
        return result
    reason = result.get("reason")
    if reason == "not_found":
        raise HTTPException(status_code=404, detail="달력 링크가 없거나 오래되었습니다.")
    if reason == "forbidden":
        raise HTTPException(status_code=403, detail="체험 달력은 마을 운영자만 등록할 수 있습니다.")
    raise HTTPException(status_code=400, detail="체험 이름, 날짜, 단체, 인원을 확인해 주세요.")


def _guide_register_response(request: Request, posted: str | None):
    unlocked, notice = codes_open(request.cookies.get("guide_unlock", ""), posted)
    response = request.app.state.templates.TemplateResponse(
        request,
        "guide_register.html",
        {
            "title": "등록 안내",
            "rows": guide_rows(unlocked),
            "unlocked": unlocked,
            "notice": notice,
        },
    )
    if posted and unlocked:
        response.set_cookie(
            "guide_unlock",
            issue_unlock_cookie(),
            max_age=12 * 60 * 60,
            httponly=True,
            samesite="lax",
        )
    return response


@router.get("/guide/register", response_class=HTMLResponse)
async def guide_register_page(request: Request):
    return _guide_register_response(request, None)


@router.post("/guide/register", response_class=HTMLResponse)
async def guide_register_submit(request: Request):
    form = await request.form()
    return _guide_register_response(request, str(form.get("password") or ""))


def _dev_response(request: Request, posted: str | None, notice_override: str | None = None):
    unlocked, notice = dev_open(request.cookies.get("dev_admin", ""), posted)
    if notice_override:
        notice = notice_override
    response = request.app.state.templates.TemplateResponse(
        request,
        "guide_dev.html",
        {
            "title": "개발 초기화",
            "rows": village_choices() if unlocked else [],
            "unlocked": unlocked,
            "notice": notice,
        },
    )
    if posted and unlocked:
        response.set_cookie(
            "dev_admin",
            issue_dev_cookie(),
            max_age=12 * 60 * 60,
            httponly=True,
            samesite="lax",
        )
    return response


@router.get("/guide/dev", response_class=HTMLResponse)
async def guide_dev_page(request: Request):
    return _dev_response(request, None)


@router.post("/guide/dev", response_class=HTMLResponse)
async def guide_dev_submit(request: Request):
    form = await request.form()
    return _dev_response(request, str(form.get("password") or ""))


@router.post("/guide/dev/reset", response_class=HTMLResponse)
async def guide_dev_reset(request: Request):
    unlocked, _notice = dev_open(request.cookies.get("dev_admin", ""), None)
    if not unlocked:
        raise HTTPException(status_code=403, detail="개발 화면이 열리지 않았습니다.")
    form = await request.form()
    notice = clear_village_records(str(form.get("village_id") or ""), str(form.get("kind") or ""))
    return _dev_response(request, None, notice)


@router.get("/guide/use", response_class=HTMLResponse)
async def guide_use_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request, "guide_use.html", {"title": "사용 안내"}
    )


@router.get("/calendar/{token}", response_class=HTMLResponse)
async def calendar_page(request: Request, token: str):
    if calendar_snapshot(token) is None:
        raise HTTPException(status_code=404, detail="달력 링크가 없거나 오래되었습니다.")
    return request.app.state.templates.TemplateResponse(
        request, "calendar.html", {"title": "체험 달력", "token": token}
    )


@router.get("/api/calendar/{token}")
async def calendar_api(token: str):
    snapshot = calendar_snapshot(token)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="달력 링크가 없거나 오래되었습니다.")
    return snapshot


@router.post("/api/calendar/{token}")
async def calendar_save(token: str, request: Request):
    body = await request.json()
    result = save_calendar_from_token(
        token,
        str(body.get("label") or ""),
        str(body.get("visit_date") or ""),
        str(body.get("group_name") or ""),
        body.get("num_people"),
    )
    return _calendar_result(result)


@router.post("/api/calendar/{token}/bookings/{booking_id}")
async def calendar_booking_status(token: str, booking_id: int, request: Request):
    body = await request.json()
    result = set_booking_status_from_token(token, booking_id, str(body.get("status") or ""))
    return _calendar_result(result)


@router.delete("/api/calendar/{token}")
async def calendar_delete(token: str, request: Request):
    body = await request.json()
    result = delete_calendar_from_token(
        token,
        str(body.get("label") or ""),
        str(body.get("visit_date") or ""),
        str(body.get("group_name") or ""),
    )
    return _calendar_result(result)


@router.get("/operator", response_class=HTMLResponse)
async def operator_page(request: Request):
    return request.app.state.templates.TemplateResponse(
        request, "operator.html", {"title": "내 마을"}
    )


@router.post("/api/recommend")
async def api_recommend(body: RecommendRequest):
    villages = list_public_villages()
    results = recommend_villages(body.query, villages)
    if not results:
        return {
            "status": "empty",
            "message": "조건에 맞는 마을을 찾지 못했습니다. 검색어를 조금 더 넓혀보세요.",
            "results": [],
        }
    enriched = []
    for item in results:
        village = next((v for v in villages if v.get("village_id") == item.get("village_id")), {})
        enriched.append(
            {
                **item,
                "sigungu": village.get("sigungu"),
                "program_type": village.get("program_type"),
                "program_name": village.get("program_name"),
                "address": village.get("address"),
                "facilities": village.get("facilities"),
                "grade": village.get("grade"),
                "latitude": village.get("latitude"),
                "longitude": village.get("longitude"),
                "trust_score": village.get("trust_score") or calculate_trust_score(village),
            }
        )
    return {"status": "success", "results": enriched}


@router.get("/api/villages/{village_id}/promo")
async def api_village_promo(village_id: str):
    promo = public_village_promo(village_id)
    if promo is None:
        raise HTTPException(status_code=404, detail="마을을 찾지 못했습니다.")
    return promo


@router.get("/api/villages")
async def api_villages(sigungu: str | None = None, program_type: str | None = None):
    source = list_public_villages(sigungu=sigungu, program_type=program_type)
    saved = list_program_status_map([str(village.get("village_id") or "") for village in source])
    villages = []
    for village in source:
        item = dict(village)
        village_id = str(village.get("village_id") or "")
        item["programs"] = programs_for(village, saved.get(village_id, []))
        villages.append(item)
    return {"status": "success", "count": len(villages), "villages": villages}


@router.get("/api/nearby")
async def api_nearby(village_id: str, radius: int = 5000):
    return get_nearby_for_village(village_id, radius)


@router.get("/api/dashboard/summary")
async def api_dashboard_summary():
    return get_public_dashboard_summary()


@router.get("/api/cron/sync")
async def api_cron_sync(authorization: str | None = Header(default=None)):
    if not CRON_SECRET:
        raise HTTPException(status_code=503, detail="CRON_SECRET이 설정되지 않았습니다.")
    if authorization != f"Bearer {CRON_SECRET}":
        raise HTTPException(status_code=403, detail="인가되지 않은 요청입니다.")
    result = sync_village_data()
    return {
        **result,
        "executed_at": datetime.now(timezone.utc).isoformat(),
    }
