import hashlib
import json
import os
import time
from pathlib import Path

import httpx

from config import TARGET_SIDO_NAMES, TARGET_SIGUNGU_LIST

_GRADE_SKIPPED = "등급 정보를 생략했습니다."
_SYNC_BUDGET_SECONDS = 20.0
_PAGE_TIMEOUT_SECONDS = 8.0
_village_resume_page: int | None = None
_grade_resume_page: int | None = None
_GRADE_NAME_KEYS = (
    "village_name",
    "마을명",
    "exprnVilageNm",
    "vilageNm",
    "expVillageNm",
    "villageNm",
)
_GRADE_SIGUNGU_KEYS = ("sigungu", "시군", "시군구", "시군구명", "signguNm", "sggNm")

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


def _service_key() -> str:
    return (
        os.getenv("PUBLIC_DATA_SERVICE_KEY")
        or os.getenv("PUBLIC_DATA_API_KEY")
        or os.getenv("DATA_GO_KR_SERVICE_KEY")
        or ""
    )


def _compact(value: object) -> str:
    return "".join(str(value or "").split())


def _first_text(row: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _grade_match_key(sigungu: str, village_name: str) -> str:
    return f"{_compact(sigungu)}|{_compact(village_name)}"


def apply_grade_matches(rows: list[dict], grade_rows: list[dict]) -> list[dict]:
    """시군구와 마을명이 같은 행만 으뜸촌으로 표시한다."""
    keys: set[str] = set()
    for grade in grade_rows:
        name = _first_text(grade, _GRADE_NAME_KEYS)
        sigungu = _first_text(grade, _GRADE_SIGUNGU_KEYS)
        if name and sigungu:
            keys.add(_grade_match_key(sigungu, name))
    merged: list[dict] = []
    for row in rows:
        item = dict(row)
        name = str(item.get("village_name") or "")
        sigungu = str(item.get("sigungu") or "")
        if name and sigungu and _grade_match_key(sigungu, name) in keys:
            item["grade"] = "으뜸촌"
        else:
            item["grade"] = None
        merged.append(item)
    return merged


def _unwrap_grade_payload(payload: object) -> object:
    if isinstance(payload, dict) and isinstance(payload.get("response"), dict):
        return payload["response"]
    return payload


def _grade_page_total(payload: dict, fetched: int) -> int:
    """오픈API 자동변환 응답은 totalCount가 본문에 있다."""
    if payload.get("totalCount") not in (None, ""):
        try:
            return int(payload["totalCount"])
        except (TypeError, ValueError):
            pass
    return _page_total(payload, fetched)


def _sync_deadline() -> float:
    return time.monotonic() + _SYNC_BUDGET_SECONDS


def _page_timeout(deadline: float) -> float | None:
    """이번 페이지에 쓸 수 있는 시간. 1초보다 짧으면 요청을 시작하지 않는다."""
    remaining = deadline - time.monotonic()
    if remaining < 1:
        return None
    return min(_PAGE_TIMEOUT_SECONDS, remaining)


def fetch_grade_rows(
    start_page: int = 1,
    deadline: float | None = None,
) -> tuple[list[dict] | None, str]:
    """으뜸촌 OpenAPI 행을 가져온다. 주소가 없거나 호출이 실패하면 생략한다.

    15117119는 api.odcloud.kr 명세라 page, perPage, returnType을 쓴다.
    남은 시간이 없으면 다음 페이지 번호를 _grade_resume_page에 남긴다.
    """
    global _grade_resume_page
    _grade_resume_page = None
    endpoint = os.getenv("PUBLIC_DATA_GRADE_ENDPOINT", "").strip()
    service_key = _service_key()
    if not service_key or not endpoint:
        return None, _GRADE_SKIPPED
    if deadline is None:
        deadline = _sync_deadline()

    page_size = 100
    collected: list[dict] = []
    start = max(1, start_page)
    page = start
    try:
        with httpx.Client(timeout=_PAGE_TIMEOUT_SECONDS) as client:
            for page in range(start, 11):
                timeout = _page_timeout(deadline)
                if timeout is None:
                    _grade_resume_page = page
                    break
                client.timeout = httpx.Timeout(timeout)
                response = client.get(
                    endpoint,
                    params={
                        "serviceKey": service_key,
                        "page": page,
                        "perPage": page_size,
                        "returnType": "JSON",
                    },
                )
                response.raise_for_status()
                payload = _unwrap_grade_payload(response.json())
                if isinstance(payload, list):
                    collected.extend(row for row in payload if isinstance(row, dict))
                    break
                if not isinstance(payload, dict):
                    return None, _GRADE_SKIPPED
                header = payload.get("header") or {}
                if header:
                    code = str(header.get("resultCode", "00"))
                    if code not in ("00", "0"):
                        return None, _GRADE_SKIPPED
                batch = _extract_items(payload)
                if not batch:
                    if not collected and _grade_resume_page is None:
                        return None, _GRADE_SKIPPED
                    break
                collected.extend(batch)
                total = _grade_page_total(payload, len(collected))
                if page * page_size >= total:
                    break
    except Exception:
        if collected:
            _grade_resume_page = page
        else:
            return None, _GRADE_SKIPPED
    if not collected and _grade_resume_page is None:
        return None, _GRADE_SKIPPED
    return collected, ""


def fetch_from_public_data_api(
    start_page: int = 1,
    deadline: float | None = None,
) -> list[dict]:
    """공공데이터 OpenAPI에서 마을 목록을 가져온다. 시간이 부족하면 다음 페이지를 남긴다."""
    global _village_resume_page
    _village_resume_page = None
    service_key = _service_key()
    endpoint = os.getenv("PUBLIC_DATA_VILLAGE_ENDPOINT", "")
    if not service_key or not endpoint:
        return []
    if deadline is None:
        deadline = _sync_deadline()

    page_size = 500
    collected: list[dict] = []
    start = max(1, start_page)
    page = start
    try:
        with httpx.Client(timeout=_PAGE_TIMEOUT_SECONDS) as client:
            for page in range(start, 11):
                timeout = _page_timeout(deadline)
                if timeout is None:
                    _village_resume_page = page
                    break
                client.timeout = httpx.Timeout(timeout)
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
        _village_resume_page = page
    return [normalize_public_data_row(row) for row in collected]


def merge_with_grade_info(rows: list[dict]) -> tuple[list[dict], str]:
    """으뜸촌 등급을 마을명·시군구로 병합한다. 실패하면 마을 목록은 유지하고 등급은 비운다."""
    fetched, message = fetch_grade_rows()
    if fetched is None:
        return [dict(row) for row in rows], message
    return apply_grade_matches(rows, fetched), ""


def _backup_folder() -> Path:
    preferred = Path(os.environ.get("VILLAGE_BACKUP_DIR", "exports"))
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        probe = preferred / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return preferred
    except OSError:
        fallback = Path("/tmp/village-backups")
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


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
    """이번 동기화 시각을 기록한 뒤 신뢰도를 계산한다."""
    from datetime import datetime, timezone

    from services.trust_score import calculate_trust_score

    synced_at = datetime.now(timezone.utc).isoformat()
    scored: list[dict] = []
    for row in rows:
        item = dict(row)
        item["synced_at"] = synced_at
        item["trust_score"] = calculate_trust_score(item)
        scored.append(item)
    return scored


def _resume_message(cursor: dict) -> str:
    return "resume " + json.dumps(cursor, ensure_ascii=False)


def _read_resume() -> dict | None:
    from services.supabase_client import latest_sync_log

    row = latest_sync_log("public_data_village")
    if not row or row.get("status") != "partial":
        return None
    message = str(row.get("message") or "")
    if not message.startswith("resume "):
        return None
    try:
        cursor = json.loads(message[len("resume ") :])
    except json.JSONDecodeError:
        return None
    return cursor if isinstance(cursor, dict) else None


def _grade_keys(rows: list[dict]) -> list[str]:
    keys: list[str] = []
    for grade in rows:
        name = _first_text(grade, _GRADE_NAME_KEYS)
        sigungu = _first_text(grade, _GRADE_SIGUNGU_KEYS)
        if name and sigungu:
            keys.append(_grade_match_key(sigungu, name))
    return keys


def _persist_rows(rows: list[dict]) -> tuple[list[dict], int]:
    from services.village_retirement import (
        apply_old_admin_names,
        drop_old_address_rows,
        retire_split_villages,
    )

    enriched = _with_trust_scores(rows)
    by_id: dict[str, dict] = {}
    for row in enriched:
        village_id = row.get("village_id")
        if village_id:
            by_id[str(village_id)] = row
    enriched = apply_old_admin_names(drop_old_address_rows(list(by_id.values())))
    if enriched:
        upsert_to_supabase(enriched)
    retired = retire_split_villages(_backup_folder())
    return enriched, len(retired)


def _refresh_review_scores(rows: list[dict]) -> None:
    from services.trust_score import recalculate_for_village

    for row in rows:
        village_id = str(row.get("village_id") or "")
        if village_id:
            recalculate_for_village(village_id)


def _partial(source: str, fetched: int, filtered: int, cursor: dict, retired: int = 0) -> dict:
    log_sync_result(
        source=source,
        total_fetched=fetched,
        total_filtered=filtered,
        status="partial",
        message=_resume_message(cursor),
    )
    return {
        "status": "partial",
        "source": source,
        "total_fetched": fetched,
        "total_filtered": filtered,
        "retired_old_rows": retired,
        "resume_page": cursor.get("page"),
    }


def _apply_saved_grade_keys(keys: set[str]) -> int:
    from services.supabase_client import list_villages, update_village_fields
    from services.trust_score import recalculate_for_village

    updated = 0
    for village in list_villages():
        village_id = str(village.get("village_id") or "")
        if not village_id:
            continue
        name = str(village.get("village_name") or "")
        sigungu = str(village.get("sigungu") or "")
        grade = "으뜸촌" if name and sigungu and _grade_match_key(sigungu, name) in keys else None
        update_village_fields(village_id, {"grade": grade})
        recalculate_for_village(village_id)
        updated += 1
    return updated


def _resume_grades(cursor: dict, deadline: float | None = None) -> dict:
    global _grade_resume_page
    keys = set(str(item) for item in cursor.get("keys") or [])
    page = int(cursor.get("page") or 1)
    fetched, message = fetch_grade_rows(start_page=page, deadline=deadline)
    if fetched is None and _grade_resume_page is None:
        log_sync_result(
            source="public_data_village",
            total_fetched=0,
            total_filtered=0,
            status="failure",
            message=message or _GRADE_SKIPPED,
        )
        return {"status": "failure", "total_fetched": 0, "total_filtered": 0, "message": message}
    keys.update(_grade_keys(fetched or []))
    if _grade_resume_page:
        return _partial(
            "public_data_village",
            len(fetched or []),
            len(keys),
            {"stage": "grades", "page": _grade_resume_page, "keys": sorted(keys)},
        )
    updated = _apply_saved_grade_keys(keys)
    log_sync_result(
        source="public_data_village",
        total_fetched=updated,
        total_filtered=updated,
        status="success",
        message="",
    )
    return {
        "status": "success",
        "source": "public_data_village",
        "total_fetched": updated,
        "total_filtered": updated,
        "retired_old_rows": 0,
    }


def sync_village_data(use_demo_fallback: bool = False) -> dict:
    """공공데이터 동기화. 30초 안에 끝나면 다음 실행이 이어서 받는다."""
    global _village_resume_page, _grade_resume_page
    try:
        _village_resume_page = None
        _grade_resume_page = None
        cursor = _read_resume()
        deadline = _sync_deadline()
        if cursor and cursor.get("stage") == "grades":
            return _resume_grades(cursor, deadline)
        start_page = 1
        if cursor and cursor.get("stage") == "villages":
            start_page = int(cursor.get("page") or 1)
        raw_rows = fetch_from_public_data_api(start_page=start_page, deadline=deadline)
        source = "public_data_village"
        if (
            not raw_rows
            and start_page == 1
            and _village_resume_page is None
            and use_demo_fallback
            and not _stored_has_real_villages()
        ):
            from services.demo_data import DEMO_VILLAGES

            raw_rows = list(DEMO_VILLAGES)
            source = "demo_seed_fallback"
        filtered_rows = filter_gwangju_jeonnam(raw_rows)
        if source != "demo_seed_fallback" and _village_resume_page:
            _saved, retired = _persist_rows(filtered_rows)
            _refresh_review_scores(_saved)
            return _partial(
                source,
                len(raw_rows),
                len(filtered_rows),
                {"stage": "villages", "page": _village_resume_page},
                retired,
            )
        if source == "demo_seed_fallback":
            graded_rows, grade_message = filtered_rows, ""
        else:
            grade_rows, grade_message = fetch_grade_rows(deadline=deadline)
            if _grade_resume_page:
                _saved, retired = _persist_rows(filtered_rows)
                _refresh_review_scores(_saved)
                return _partial(
                    source,
                    len(raw_rows),
                    len(filtered_rows),
                    {
                        "stage": "grades",
                        "page": _grade_resume_page,
                        "keys": _grade_keys(grade_rows or []),
                    },
                    retired,
                )
            if grade_rows is None:
                graded_rows = [dict(row) for row in filtered_rows]
            else:
                graded_rows = apply_grade_matches(filtered_rows, grade_rows)
                grade_message = ""
        enriched_rows, retired = _persist_rows(graded_rows)
        _refresh_review_scores(enriched_rows)
        log_sync_result(
            source=source,
            total_fetched=len(raw_rows),
            total_filtered=len(filtered_rows),
            status="success",
            message=grade_message,
        )
        return {
            "status": "success",
            "source": source,
            "total_fetched": len(raw_rows),
            "total_filtered": len(filtered_rows),
            "retired_old_rows": retired,
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
