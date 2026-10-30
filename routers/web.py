import time
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from config import CRON_SECRET
from models.schemas import RecommendRequest
from services.booking import get_public_dashboard_summary
from services.public_data_sync import sync_village_data
from services.recommend import recommend_villages
from services.supabase_client import get_supabase_client, list_program_status_map, list_public_villages
from services.tourapi import get_nearby_for_village
from services.dev_admin import clear_village_records, dev_open, issue_dev_cookie, village_choices
from services.guide_access import codes_open, guide_rows, issue_unlock_cookie
from services.calendar_board import (
    answer_booking_change,
    calendar_snapshot,
    change_snapshot,
    delete_calendar_from_token,
    propose_booking_from_token,
    save_calendar_from_token,
    set_booking_status_from_token,
)
from services.guest_book import guest_snapshot, save_guest_booking
from services.kakao_home import home_kakao_guide
from services.site_index import robots_txt, sitemap_xml
from services.village_promo import list_published_villages, public_village_promo
from services.village_programs import programs_for
from services.trust_score import calculate_trust_score

router = APIRouter()

_VILLAGE_LIST_TTL = 60.0
_village_list_cache: dict[tuple[str, str], tuple[float, dict]] = {}


def _cdn(fresh: int, stale: int) -> dict[str, str]:
    """브라우저가 미국 서버를 기다리지 않게 서울 CDN이 응답을 보관한다."""
    shared = f"public, s-maxage={fresh}, stale-while-revalidate={stale}"
    return {
        "Cache-Control": f"public, max-age=0, s-maxage={fresh}, stale-while-revalidate={stale}",
        "Vercel-CDN-Cache-Control": shared,
    }


# 홈은 예약 문장이 있어서 짧게만 보관한다. 나머지 공개 화면은 더 오래 둔다.
_HOME_CDN = _cdn(15, 45)
_PAGE_CDN = _cdn(300, 3600)
_VILLAGE_CDN = _cdn(120, 600)


def _html(request: Request, template: str, context: dict, headers: dict[str, str]):
    response = request.app.state.templates.TemplateResponse(request, template, context)
    response.headers.update(headers)
    return response


@router.get("/sitemap.xml")
def sitemap():
    return Response(content=sitemap_xml(), media_type="application/xml", headers=_PAGE_CDN)


@router.get("/robots.txt")
def robots():
    return PlainTextResponse(robots_txt(), headers=_PAGE_CDN)


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    context = {"title": "체험마을 AI사무장", "kakao_guide": home_kakao_guide()}
    if request.app.state.templates.env.globals.get("presentation_mode"):
        from services.presentation_board import presentation_board

        context["demo"] = presentation_board()
    return _html(request, "index.html", context, _HOME_CDN)


@router.post("/api/presentation/calendar")
async def presentation_calendar(request: Request):
    if not request.app.state.templates.env.globals.get("presentation_mode"):
        raise HTTPException(status_code=404, detail="달력을 열 수 없습니다.")
    body = await request.json()
    from services.presentation_board import presentation_calendars

    found = presentation_calendars(str(body.get("password") or ""))
    if not found:
        raise HTTPException(status_code=404, detail="달력을 열 수 없습니다.")
    return found


@router.get("/recommend", response_class=HTMLResponse)
async def recommend_page(request: Request):
    return _html(request, "recommend.html", {"title": "AI 추천"}, _PAGE_CDN)


@router.get("/map", response_class=HTMLResponse)
async def map_page(request: Request):
    return _html(request, "map.html", {"title": "마을 지도"}, _PAGE_CDN)


@router.get("/nearby", response_class=HTMLResponse)
async def nearby_page(request: Request):
    return _html(request, "nearby.html", {"title": "주변정보"}, _PAGE_CDN)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return _html(request, "dashboard.html", {"title": "운영 현황"}, _PAGE_CDN)


@router.get("/villages", response_class=HTMLResponse)
async def villages_page(request: Request):
    return _html(
        request,
        "villages.html",
        {"title": "마을 소개", "villages": list_published_villages()},
        _VILLAGE_CDN,
    )


@router.get("/village/{village_id}", response_class=HTMLResponse)
async def village_page(request: Request, village_id: str):
    promo = public_village_promo(village_id)
    if promo is None:
        raise HTTPException(status_code=404, detail="마을을 찾지 못했습니다.")
    return _html(
        request,
        "village.html",
        {"title": promo["village_name"] or "마을", "promo": promo},
        _VILLAGE_CDN,
    )


def _calendar_result(result: dict):
    if result.get("ok"):
        return result
    reason = result.get("reason")
    if reason == "not_found":
        raise HTTPException(status_code=404, detail="달력 링크가 없거나 오래되었습니다.")
    if reason == "forbidden":
        raise HTTPException(status_code=403, detail="체험 달력은 마을 운영자만 등록할 수 있습니다.")
    if reason == "program_not_found":
        raise HTTPException(status_code=400, detail="이 마을에서 운영 중인 체험이 아닙니다.")
    if reason == "bad_slot":
        raise HTTPException(status_code=400, detail="날짜와 시간을 확인해 주세요.")
    if reason == "not_pending":
        raise HTTPException(status_code=400, detail="대기 예약만 일정을 바꿀 수 있습니다.")
    if reason == "closed":
        raise HTTPException(status_code=400, detail="이 일정 변경은 이미 끝났습니다.")
    if reason == "bad_decision":
        raise HTTPException(status_code=400, detail="변경 승인 또는 변경 거부를 선택해 주세요.")
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


def _embed(embed: str) -> bool:
    return embed == "1"


@router.get("/calendar/{token}", response_class=HTMLResponse)
async def calendar_page(request: Request, token: str, embed: str = "", view: str = ""):
    if calendar_snapshot(token) is None:
        raise HTTPException(status_code=404, detail="달력 링크가 없거나 오래되었습니다.")
    return request.app.state.templates.TemplateResponse(
        request,
        "calendar.html",
        {
            "title": "체험 달력",
            "token": token,
            "mode": "operator",
            "embed": _embed(embed),
            "view": "program" if view == "program" else "",
        },
    )


@router.get("/book/{token}", response_class=HTMLResponse)
async def guest_book_page(request: Request, token: str, embed: str = ""):
    if guest_snapshot(token) is None:
        raise HTTPException(status_code=404, detail="달력 링크가 없거나 오래되었습니다.")
    return request.app.state.templates.TemplateResponse(
        request,
        "calendar.html",
        {"title": "예약 달력", "token": token, "mode": "guest", "embed": _embed(embed)},
    )


@router.get("/api/book/{token}")
async def guest_book_api(token: str):
    snapshot = guest_snapshot(token)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="달력 링크가 없거나 오래되었습니다.")
    return snapshot


@router.post("/api/book/{token}")
async def guest_book_save(token: str, request: Request):
    body = await request.json()
    result = save_guest_booking(
        token,
        str(body.get("label") or ""),
        str(body.get("visit_date") or ""),
        str(body.get("visit_time") or ""),
        body.get("num_people"),
    )
    return _calendar_result(result)


@router.get("/api/calendar/{token}")
async def calendar_api(token: str, view: str = ""):
    snapshot = calendar_snapshot(token, view)
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


@router.post("/api/calendar/{token}/bookings/{booking_id}/proposal")
async def calendar_booking_proposal(token: str, booking_id: int, request: Request):
    body = await request.json()
    result = propose_booking_from_token(
        token,
        booking_id,
        str(body.get("visit_date") or ""),
        str(body.get("visit_time") or ""),
    )
    return _calendar_result(result)


@router.get("/change/{token}", response_class=HTMLResponse)
async def change_page(request: Request, token: str):
    if change_snapshot(token) is None:
        raise HTTPException(status_code=404, detail="달력 링크가 없거나 오래되었습니다.")
    return request.app.state.templates.TemplateResponse(
        request,
        "calendar.html",
        {"title": "일정 변경", "token": token, "mode": "change", "embed": False},
    )


@router.get("/api/change/{token}")
async def change_api(token: str):
    snapshot = change_snapshot(token)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="달력 링크가 없거나 오래되었습니다.")
    return snapshot


@router.post("/api/change/{token}")
async def change_answer(token: str, request: Request):
    body = await request.json()
    result = answer_booking_change(token, str(body.get("decision") or ""))
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


def _village_list_payload(sigungu: str | None, program_type: str | None) -> dict:
    key = (sigungu or "", program_type or "")
    now = time.monotonic()
    cached = _village_list_cache.get(key)
    live = get_supabase_client() is not None
    if live and cached is not None and now - cached[0] < _VILLAGE_LIST_TTL:
        return cached[1]
    source = list_public_villages(sigungu=sigungu, program_type=program_type)
    saved = list_program_status_map([str(village.get("village_id") or "") for village in source])
    villages = []
    for village in source:
        item = dict(village)
        village_id = str(village.get("village_id") or "")
        item["programs"] = programs_for(village, saved.get(village_id, []))
        villages.append(item)
    payload = {"status": "success", "count": len(villages), "villages": villages}
    if live:
        _village_list_cache[key] = (now, payload)
    return payload


@router.get("/api/villages")
async def api_villages(response: Response, sigungu: str | None = None, program_type: str | None = None):
    response.headers.update(_VILLAGE_CDN)
    return _village_list_payload(sigungu, program_type)


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
