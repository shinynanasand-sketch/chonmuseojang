import os

import httpx

from services.supabase_client import get_village_by_id


def fetch_nearby_attractions(latitude: float, longitude: float, radius: int = 5000) -> dict:
    """TourAPI로 주변 관광정보를 조회한다 (FR-03)."""
    service_key = os.getenv("TOUR_API_SERVICE_KEY", "")
    endpoint = os.getenv("TOUR_API_ENDPOINT", "")
    if not service_key or not endpoint:
        return {"attractions": [], "restaurants": []}

    try:
        params = {
            "serviceKey": service_key,
            "mapX": longitude,
            "mapY": latitude,
            "radius": radius,
            "MobileOS": "ETC",
            "MobileApp": "chonmuseojang",
            "_type": "json",
        }
        with httpx.Client(timeout=10.0) as client:
            response = client.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json()
            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            if isinstance(items, dict):
                items = [items]
            attractions = [i for i in items if i.get("contenttypeid") in ("12", "14", "15", "25", "28", "32", "38", "39")]
            restaurants = [i for i in items if i.get("contenttypeid") == "39"]
            return {
                "attractions": [
                    {"title": i.get("title"), "addr": i.get("addr1"), "content_type": "관광지"}
                    for i in attractions[:10]
                ],
                "restaurants": [
                    {"title": i.get("title"), "addr": i.get("addr1"), "content_type": "음식점"}
                    for i in restaurants[:10]
                ],
            }
    except Exception:
        return {"attractions": [], "restaurants": []}


def get_nearby_for_village(village_id: str, radius: int = 5000) -> dict:
    village = get_village_by_id(village_id)
    if not village or village.get("latitude") is None or village.get("longitude") is None:
        return {"status": "empty", "village_id": village_id, "attractions": [], "restaurants": []}
    nearby = fetch_nearby_attractions(village["latitude"], village["longitude"], radius)
    return {"status": "success", "village_id": village_id, **nearby}
