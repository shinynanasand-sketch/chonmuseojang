import hashlib

from config import TARGET_SIDO_NAMES, TARGET_SIGUNGU_LIST

# 전국농어촌체험휴양마을표준데이터 (data.go.kr 15013113) 응답 키
FIELD_ALIASES: dict[str, str] = {
    "village_id": "village_id",
    "mngNo": "village_id",
    "managementNo": "village_id",
    "village_name": "village_name",
    "exprnVilageNm": "village_name",
    "expVillageNm": "village_name",
    "villageNm": "village_name",
    "sido": "sido",
    "ctprvnNm": "sido",
    "ctpvNm": "sido",
    "sigungu": "sigungu",
    "signguNm": "sigungu",
    "sggNm": "sigungu",
    "program_type": "program_type",
    "exprnSe": "program_type",
    "expType": "program_type",
    "program_name": "program_name",
    "exprnCn": "program_name",
    "expNm": "program_name",
    "address": "address",
    "rdnmadr": "address",
    "lnmadr": "address",
    "roadAddr": "address",
    "latitude": "latitude",
    "lat": "latitude",
    "mapY": "latitude",
    "longitude": "longitude",
    "lot": "longitude",
    "mapX": "longitude",
    "phone": "phone",
    "phoneNumber": "phone",
    "telno": "phone",
    "homepage_url": "homepage_url",
    "homepageUrl": "homepage_url",
    "facilities": "facilities",
    "holdFclty": "facilities",
    "grade": "grade",
}

_TEXT_FIELDS = (
    "village_id",
    "village_name",
    "sido",
    "sigungu",
    "program_type",
    "program_name",
    "address",
    "phone",
    "homepage_url",
    "facilities",
    "grade",
)


def _stable_village_id(name: str, sigungu: str, address: str) -> str:
    raw = f"{name}|{sigungu}|{address}".encode("utf-8")
    return "PD" + hashlib.sha256(raw).hexdigest()[:12]


def normalize_public_data_row(raw: dict) -> dict:
    """공공데이터 응답 행을 villages_cache 스키마로 정규화한다."""
    normalized: dict = {}
    for key, value in raw.items():
        target = FIELD_ALIASES.get(key)
        if target is None or value in (None, ""):
            continue
        if target in normalized and normalized[target] not in (None, ""):
            continue
        if target in _TEXT_FIELDS:
            normalized[target] = value
        elif target in ("latitude", "longitude"):
            try:
                normalized[target] = float(value)
            except (TypeError, ValueError):
                continue
    if "village_id" not in normalized and normalized.get("village_name"):
        normalized["village_id"] = _stable_village_id(
            str(normalized.get("village_name", "")),
            str(normalized.get("sigungu", "")),
            str(normalized.get("address", "")),
        )
    if "sigungu" not in normalized:
        normalized["sigungu"] = ""
    return normalized


def filter_gwangju_jeonnam(rows: list[dict]) -> list[dict]:
    """광주·전남 지역 마을만 필터링한다 (FR-13).

    동구·서구·남구·북구는 다른 광역시에도 있으므로, 시도명이 있으면
    광주·전남 명칭일 때만 통과시킨다.
    """
    filtered = []
    for row in rows:
        sido = (row.get("sido") or "").strip()
        sigungu = (row.get("sigungu") or "").strip()
        if sido in TARGET_SIDO_NAMES or (not sido and sigungu in TARGET_SIGUNGU_LIST):
            filtered.append(row)
    return filtered


def _coerce_item_list(value) -> list[dict] | None:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        if "item" in value:
            return _coerce_item_list(value["item"])
        return [value]
    return None


def _extract_items(data: dict) -> list[dict]:
    if not isinstance(data, dict):
        return []
    body = data.get("body")
    if isinstance(body, dict) and "items" in body:
        found = _coerce_item_list(body.get("items"))
        if found is not None:
            return found
    for key in ("data", "items", "response", "body"):
        if key not in data:
            continue
        found = _coerce_item_list(data[key])
        if found:
            return found
    return []


def _page_total(payload: dict, fetched: int) -> int:
    body = payload.get("body") if isinstance(payload, dict) else None
    if isinstance(body, dict) and body.get("totalCount") not in (None, ""):
        try:
            return int(body["totalCount"])
        except (TypeError, ValueError):
            return fetched
    return fetched


def fetch_from_public_data_api() -> list[dict]:
    """공공데이터 OpenAPI에서 마을 목록을 가져온다."""
    import os as _os

    import httpx

    service_key = (
        _os.getenv("PUBLIC_DATA_SERVICE_KEY")
        or _os.getenv("PUBLIC_DATA_API_KEY")
        or _os.getenv("DATA_GO_KR_SERVICE_KEY")
        or ""
    )
    endpoint = _os.getenv("PUBLIC_DATA_VILLAGE_ENDPOINT", "")
    if not service_key or not endpoint:
        return []

    page_size = 500
    collected: list[dict] = []
    try:
        with httpx.Client(timeout=60.0) as client:
            for page in range(1, 11):
                response = client.get(
                    endpoint,
                    params={
                        "serviceKey": service_key,
                        "pageNo": page,
                        "numOfRows": page_size,
                        "type": "json",
                    },
                )
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, list):
                    collected.extend(row for row in payload if isinstance(row, dict))
                    break
                if not isinstance(payload, dict):
                    break
                header = payload.get("header") or {}
                code = str(header.get("resultCode", "00"))
                if code not in ("00", "0"):
                    break
                batch = _extract_items(payload)
                collected.extend(batch)
                total = _page_total(payload, len(collected))
                if not batch or page * page_size >= total:
                    break
    except Exception:
        if not collected:
            return []
    return [normalize_public_data_row(row) for row in collected]


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


def _stored_has_real_villages() -> bool:
    from services.demo_data import is_demo_village
    from services.supabase_client import list_villages

    return any(not is_demo_village(row) for row in list_villages())


def _with_trust_scores(rows: list[dict]) -> list[dict]:
    """점수가 비어 있으면 신뢰도를 계산해 채운다. 이미 있는 점수는 유지한다."""
    from services.trust_score import calculate_trust_score

    scored: list[dict] = []
    for row in rows:
        item = dict(row)
        if not item.get("trust_score"):
            item["trust_score"] = calculate_trust_score(item)
        scored.append(item)
    return scored


def sync_village_data(use_demo_fallback: bool = False) -> dict:
    """공공데이터 동기화 파이프라인 (FR-12)."""
    try:
        raw_rows = fetch_from_public_data_api()
        source = "public_data_village"
        if not raw_rows and use_demo_fallback and not _stored_has_real_villages():
            from services.demo_data import DEMO_VILLAGES

            raw_rows = list(DEMO_VILLAGES)
            source = "demo_seed_fallback"
        filtered_rows = filter_gwangju_jeonnam(raw_rows)
        enriched_rows = _with_trust_scores(merge_with_grade_info(filtered_rows))
        by_id: dict[str, dict] = {}
        for row in enriched_rows:
            village_id = row.get("village_id")
            if village_id:
                by_id[str(village_id)] = row
        enriched_rows = list(by_id.values())
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
