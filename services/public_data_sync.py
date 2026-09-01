from config import TARGET_SIDO_NAMES, TARGET_SIGUNGU_LIST

# 공공데이터 원본 키 → 우리 시스템 필드명 (DDD 2장, 실제 API 호출 후 확정)
FIELD_ALIASES: dict[str, str] = {
    "village_id": "village_id",
    "mngNo": "village_id",
    "managementNo": "village_id",
    "village_name": "village_name",
    "expVillageNm": "village_name",
    "villageNm": "village_name",
    "sido": "sido",
    "ctpvNm": "sido",
    "sigungu": "sigungu",
    "sggNm": "sigungu",
    "program_type": "program_type",
    "expType": "program_type",
    "program_name": "program_name",
    "expNm": "program_name",
    "address": "address",
    "roadAddr": "address",
    "latitude": "latitude",
    "lat": "latitude",
    "mapY": "latitude",
    "longitude": "longitude",
    "lot": "longitude",
    "mapX": "longitude",
    "phone": "phone",
    "telno": "phone",
    "grade": "grade",
}


def normalize_public_data_row(raw: dict) -> dict:
    """공공데이터 응답 행을 villages_cache 스키마로 정규화한다."""
    normalized: dict = {}
    for key, value in raw.items():
        target = FIELD_ALIASES.get(key, key)
        if target in (
            "village_id",
            "village_name",
            "sido",
            "sigungu",
            "program_type",
            "program_name",
            "address",
            "phone",
            "grade",
        ):
            normalized[target] = value
        elif target in ("latitude", "longitude"):
            try:
                normalized[target] = float(value) if value not in (None, "") else None
            except (TypeError, ValueError):
                normalized[target] = None
    if "village_id" not in normalized and normalized.get("village_name"):
        normalized["village_id"] = f"GEN_{hash(normalized['village_name']) % 100000:05d}"
    if "sigungu" not in normalized:
        normalized["sigungu"] = ""
    return normalized


def filter_gwangju_jeonnam(rows: list[dict]) -> list[dict]:
    """광주·전남 지역 마을만 필터링한다 (FR-13)."""
    filtered = []
    for row in rows:
        sido = row.get("sido", "")
        sigungu = row.get("sigungu", "")
        if sido in TARGET_SIDO_NAMES or sigungu in TARGET_SIGUNGU_LIST:
            filtered.append(row)
    return filtered


def _extract_items(data: dict) -> list[dict]:
    for key in ("data", "items", "response", "body"):
        if key in data and isinstance(data[key], list):
            return data[key]
        if key in data and isinstance(data[key], dict):
            nested = data[key]
            for inner in ("items", "item", "data"):
                if inner in nested:
                    items = nested[inner]
                    return items if isinstance(items, list) else [items]
    return []


def fetch_from_public_data_api() -> list[dict]:
    """공공데이터 OpenAPI에서 마을 목록을 가져온다."""
    import os as _os

    import httpx

    service_key = _os.getenv("PUBLIC_DATA_SERVICE_KEY", "")
    endpoint = _os.getenv("PUBLIC_DATA_VILLAGE_ENDPOINT", "")
    if not service_key or not endpoint:
        return []

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(endpoint, params={"serviceKey": service_key})
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                rows = data
            elif isinstance(data, dict):
                rows = _extract_items(data)
            else:
                rows = []
            return [normalize_public_data_row(r) for r in rows]
    except Exception:
        return []


def merge_with_grade_info(rows: list[dict]) -> list[dict]:
    """보조 등급 데이터 병합 (현재는 원본 그대로 반환)."""
    return rows


def upsert_to_supabase(rows: list[dict]) -> None:
    """Supabase villages_cache에 upsert한다."""
    from services.supabase_client import upsert_villages

    upsert_villages(rows)


def log_sync_result(
    source: str,
    total_fetched: int,
    total_filtered: int,
    status: str,
    message: str = "",
) -> None:
    """동기화 결과를 sync_logs에 기록한다."""
    from services.supabase_client import insert_sync_log

    insert_sync_log(
        {
            "source": source,
            "total_fetched": total_fetched,
            "total_filtered": total_filtered,
            "status": status,
            "message": message,
        }
    )


def sync_village_data(use_demo_fallback: bool = True) -> dict:
    """공공데이터 동기화 파이프라인 (FR-12)."""
    try:
        raw_rows = fetch_from_public_data_api()
        source = "public_data_village"
        if not raw_rows and use_demo_fallback:
            from services.demo_data import DEMO_VILLAGES

            raw_rows = list(DEMO_VILLAGES)
            source = "demo_seed_fallback"
        filtered_rows = filter_gwangju_jeonnam(raw_rows)
        enriched_rows = merge_with_grade_info(filtered_rows)
        if enriched_rows:
            upsert_to_supabase(enriched_rows)
        log_sync_result(
            source=source,
            total_fetched=len(raw_rows),
            total_filtered=len(filtered_rows),
            status="success",
        )
        return {
            "status": "success",
            "source": source,
            "total_fetched": len(raw_rows),
            "total_filtered": len(filtered_rows),
        }
    except Exception as exc:
        log_sync_result(
            source="public_data_village",
            total_fetched=0,
            total_filtered=0,
            status="failure",
            message=str(exc),
        )
        return {"status": "failure", "total_fetched": 0, "total_filtered": 0, "message": str(exc)}
