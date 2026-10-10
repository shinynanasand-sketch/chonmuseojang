import os

import httpx

from services.supabase_client import get_village_by_id

ATTRACTION_TYPE_IDS = {"12", "14", "15", "25", "28", "32", "38"}
RESTAURANT_TYPE_ID = "39"
TARGET_AREA_CODES = {"5", "38"}
CONTENT_LABELS = {
    "12": "관광지",
    "14": "문화시설",
    "15": "축제",
    "25": "여행코스",
    "28": "레포츠",
    "32": "숙박",
    "38": "쇼핑",
    "39": "음식점",
}


def _service_key() -> str:
    return (
        os.getenv("TOUR_API_SERVICE_KEY")
        or os.getenv("PUBLIC_DATA_API_KEY")
        or os.getenv("PUBLIC_DATA_SERVICE_KEY")
        or os.getenv("DATA_GO_KR_SERVICE_KEY")
        or ""
    ).strip()


def _endpoint() -> str:
    explicit = (os.getenv("TOUR_API_ENDPOINT") or "").strip()
    if explicit:
        return explicit
    base = (os.getenv("TOUR_API_BASE") or "").strip().rstrip("/")
    if not base:
        return ""
    return f"{base}/locationBasedList2"


def _empty(status: str) -> dict:
    return {"status": status, "attractions": [], "restaurants": []}


def _allowed_area(item: dict) -> bool:
    area = str(item.get("areacode") or "").strip()
    return not area or area in TARGET_AREA_CODES


def _image_url(item: dict) -> str:
    for key in ("firstimage", "firstimage2"):
        value = str(item.get(key) or "").strip()
        if value.startswith("http://") or value.startswith("https://"):
            return value
    return ""


def _distance_m(item: dict) -> float | None:
    raw = item.get("dist")
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _summarize(item: dict) -> dict:
    type_id = str(item.get("contenttypeid") or "")
    return {
        "title": item.get("title"),
        "addr": item.get("addr1"),
        "content_type": CONTENT_LABELS.get(type_id, "관광정보"),
        "image_url": _image_url(item),
        "distance_m": _distance_m(item),
    }


def fetch_nearby_attractions(latitude: float, longitude: float, radius: int = 5000) -> dict:
    """TourAPI로 주변 관광정보를 조회한다 (FR-03)."""
    service_key = _service_key()
    endpoint = _endpoint()
    if not service_key or not endpoint:
        return _empty("unavailable")

    try:
        params = {
            "serviceKey": service_key,
            "mapX": longitude,
            "mapY": latitude,
            "radius": radius,
            "numOfRows": 30,
            "pageNo": 1,
            "MobileOS": "ETC",
            "MobileApp": "chonmuseojang",
            "_type": "json",
        }
        with httpx.Client(timeout=10.0) as client:
            response = client.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json()
        header = data.get("response", {}).get("header", {})
        if str(header.get("resultCode", "")) not in ("0000", "00", "0"):
            return _empty("unavailable")
        items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list):
            items = []
        kept = [item for item in items if isinstance(item, dict) and _allowed_area(item)]
        attractions = [
            _summarize(item)
            for item in kept
            if str(item.get("contenttypeid") or "") in ATTRACTION_TYPE_IDS
        ][:10]
        restaurants = [
            _summarize(item)
            for item in kept
            if str(item.get("contenttypeid") or "") == RESTAURANT_TYPE_ID
        ][:10]
        return {"status": "success", "attractions": attractions, "restaurants": restaurants}
    except Exception:
        return _empty("unavailable")


def get_nearby_for_village(village_id: str, radius: int = 5000) -> dict:
    village = get_village_by_id(village_id)
    if not village or village.get("latitude") is None or village.get("longitude") is None:
        return {
            "status": "empty",
            "village_id": village_id,
            "attractions": [],
            "restaurants": [],
        }
    nearby = fetch_nearby_attractions(village["latitude"], village["longitude"], radius)
    return {"village_id": village_id, **nearby}
