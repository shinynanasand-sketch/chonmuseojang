from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import HTMLResponse

from config import CRON_SECRET
from models.schemas import RecommendRequest
from services.booking import get_public_dashboard_summary
from services.public_data_sync import sync_village_data
from services.recommend import recommend_villages
from services.supabase_client import list_villages
from services.tourapi import get_nearby_for_village
from services.trust_score import calculate_trust_score

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return request.app.state.templates.TemplateResponse(
        request, "index.html", {"title": "체험마을 AI사무장"}
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


@router.post("/api/recommend")
async def api_recommend(body: RecommendRequest):
    villages = list_villages()
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
                "latitude": village.get("latitude"),
                "longitude": village.get("longitude"),
                "trust_score": village.get("trust_score") or calculate_trust_score(village),
            }
        )
    return {"status": "success", "results": enriched}


@router.get("/api/villages")
async def api_villages(sigungu: str | None = None, program_type: str | None = None):
    villages = list_villages(sigungu=sigungu, program_type=program_type)
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
