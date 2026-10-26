"""Supabase 클라이언트 및 인메모리 폴백 (로컬/테스트용)."""

import os
import time
from typing import Any

_villages_cache: list[dict] = []
_sync_logs: list[dict] = []
_bookings: list[dict] = []
_reviews: list[dict] = []
_booking_id_counter = 1
_review_id_counter = 1
_contents: list[dict] = []
_content_id_counter = 1
_program_status: list[dict] = []
_program_notes: list[dict] = []
_calendar: list[dict] = []
_calendar_id_counter = 1
_client = None
_recommend_cache: tuple[float, list[dict]] | None = None
_RECOMMEND_TTL = 60.0
_POSTGREST_TIMEOUT = 2
_RECOMMEND_COLUMNS = (
    "village_id,village_name,sido,sigungu,program_type,program_name,"
    "facilities,address,grade,trust_score,synced_at,average_rating"
)
_operators: list[dict] = [
    {
        "operator_id": 1,
        "village_id": "V001",
        "kakao_user_id": "kakao_owner_v001",
        "login_id": "owner_v001",
        "operator_name": "V001 운영자",
        "registered_at": "2026-09-01T00:00:00+00:00",
        "is_active": True,
        "role": "village",
    },
    {
        "operator_id": 2,
        "village_id": "V002",
        "kakao_user_id": "kakao_owner_v002",
        "login_id": "owner_v002",
        "operator_name": "V002 운영자",
        "registered_at": "2026-09-01T00:00:00+00:00",
        "is_active": True,
        "role": "village",
    },
    {
        "operator_id": 3,
        "village_id": "V001",
        "kakao_user_id": "owner_test",
        "login_id": "owner_test",
        "operator_name": "테스트 운영자",
        "registered_at": "2026-09-01T00:00:00+00:00",
        "is_active": True,
        "role": "village",
    },
]


def _use_supabase() -> bool:
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


def _create_supabase_client():
    from supabase import ClientOptions, create_client

    options = ClientOptions(
        postgrest_client_timeout=_POSTGREST_TIMEOUT,
        storage_client_timeout=_POSTGREST_TIMEOUT,
    )
    return create_client(
        os.getenv("SUPABASE_URL", ""),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        options=options,
    )


def get_supabase_client():
    """프로세스당 클라이언트 하나. PostgREST 대기는 2초에서 끊는다."""
    global _client
    if not _use_supabase():
        return None
    if _client is None:
        _client = _create_supabase_client()
    return _client


def _without_registration_code(row: dict) -> dict:
    cleaned = dict(row)
    cleaned.pop("registration_code", None)
    return cleaned


def upsert_villages(rows: list[dict]) -> None:
    """공공데이터 동기화. registration_code는 건드리지 않는다."""
    global _villages_cache
    client = get_supabase_client()
    payload = [_without_registration_code(row) for row in rows]
    if client:
        client.table("villages_cache").upsert(payload).execute()
        _clear_recommend_cache()
        return
    by_id = {v["village_id"]: v for v in _villages_cache}
    for row in payload:
        existing = by_id.get(row["village_id"], {})
        merged = {**existing, **row}
        if "registration_code" in existing:
            merged["registration_code"] = existing["registration_code"]
        by_id[row["village_id"]] = merged
    _villages_cache = list(by_id.values())


def update_village_place(village_id: str, sido: str, address: str) -> None:
    """시도명과 주소만 고친다. 등록 코드와 다른 열은 그대로 둔다."""
    client = get_supabase_client()
    if client:
        client.table("villages_cache").update({"sido": sido, "address": address}).eq(
            "village_id", village_id
        ).execute()
        _clear_recommend_cache()
        return
    for row in _villages_cache:
        if row.get("village_id") == village_id:
            row["sido"] = sido
            row["address"] = address
            _clear_recommend_cache()
            return


def set_registration_code(village_id: str, code: str, village: dict | None = None) -> None:
    """자가 등록 코드를 저장한다. 동기화 upsert에서는 호출하지 않는다."""
    client = get_supabase_client()
    if client:
        client.table("villages_cache").update({"registration_code": code}).eq(
            "village_id", village_id
        ).execute()
        return
    for row in _villages_cache:
        if row.get("village_id") == village_id:
            row["registration_code"] = code
            return
    created = dict(village or {})
    created["village_id"] = village_id
    created["registration_code"] = code
    _villages_cache.append(created)


def detach_operators_for_village(village_id: str) -> list[dict]:
    """테스트에서 마을 담당 운영자를 잠시 비운다."""
    global _operators
    kept: list[dict] = []
    detached: list[dict] = []
    for operator in _operators:
        if operator.get("village_id") == village_id:
            detached.append(operator)
        else:
            kept.append(operator)
    _operators = kept
    return detached


def restore_operators(rows: list[dict]) -> None:
    global _operators
    existing = {operator.get("operator_id") for operator in _operators}
    for row in rows:
        if row.get("operator_id") not in existing:
            _operators.append(row)


def list_public_villages(sigungu: str | None = None, program_type: str | None = None) -> list[dict]:
    """관광객 화면용 마을 목록. 실데이터가 있으면 예시 마을을 제외한다."""
    from services.demo_data import public_village_rows

    return public_village_rows(list_villages(sigungu=sigungu, program_type=program_type))


def _clear_recommend_cache() -> None:
    global _recommend_cache
    _recommend_cache = None


def list_recommend_villages() -> list[dict]:
    """카카오 추천용 마을. 필요한 열만 읽고 같은 프로세스에서 60초 재사용한다."""
    global _recommend_cache
    now = time.monotonic()
    if (
        _use_supabase()
        and _recommend_cache is not None
        and now - _recommend_cache[0] < _RECOMMEND_TTL
    ):
        return _recommend_cache[1]
    from services.demo_data import public_village_rows

    rows = public_village_rows(_recommend_rows())
    if _use_supabase():
        _recommend_cache = (now, rows)
    return rows


def _recommend_rows() -> list[dict]:
    client = get_supabase_client()
    if client:
        result = client.table("villages_cache").select(_RECOMMEND_COLUMNS).execute()
        return result.data or []
    return list(_villages_cache)


def list_villages_by_name(village_name: str, sigungu: str | None = None) -> list[dict]:
    """마을명과 같거나, 시군과 마을명이 함께 맞는 행만 읽는다."""
    name = village_name.strip()
    client = get_supabase_client()
    if client:
        query = client.table("villages_cache").select("*").eq("village_name", name)
        if sigungu is not None:
            query = query.eq("sigungu", sigungu.strip())
        return query.execute().data or []
    rows = [
        row
        for row in _villages_cache
        if str(row.get("village_name") or "").strip() == name
    ]
    if sigungu is not None:
        wanted = sigungu.strip()
        rows = [row for row in rows if str(row.get("sigungu") or "").strip() == wanted]
    return rows


def list_villages(sigungu: str | None = None, program_type: str | None = None) -> list[dict]:
    client = get_supabase_client()
    if client:
        query = client.table("villages_cache").select("*")
        if sigungu:
            query = query.eq("sigungu", sigungu)
        if program_type:
            query = query.eq("program_type", program_type)
        return query.execute().data or []
    rows = list(_villages_cache)
    if sigungu:
        rows = [r for r in rows if r.get("sigungu") == sigungu]
    if program_type:
        rows = [r for r in rows if r.get("program_type") == program_type]
    return rows


def get_village_by_id(village_id: str) -> dict | None:
    client = get_supabase_client()
    if client:
        result = (
            client.table("villages_cache")
            .select("*")
            .eq("village_id", village_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return rows[0] if rows else None
    for village in _villages_cache:
        if village.get("village_id") == village_id:
            return village
    return None


def insert_sync_log(entry: dict[str, Any]) -> None:
    global _sync_logs
    client = get_supabase_client()
    if client:
        client.table("sync_logs").insert(entry).execute()
        return
    _sync_logs.append(entry)


def get_operator_by_kakao_id(kakao_user_id: str) -> dict | None:
    client = get_supabase_client()
    if client:
        result = (
            client.table("operators")
            .select("*")
            .eq("kakao_user_id", kakao_user_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    for op in _operators:
        if op.get("kakao_user_id") == kakao_user_id and op.get("is_active"):
            return op
    return None


def get_operator_by_id(operator_id: int) -> dict | None:
    client = get_supabase_client()
    if client:
        result = (
            client.table("operators")
            .select("*")
            .eq("operator_id", operator_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    for operator in _operators:
        if operator.get("operator_id") == operator_id and operator.get("is_active"):
            return operator
    return None


def _is_village_role(operator: dict) -> bool:
    return (operator.get("role") or "village") == "village"


def list_village_operator_ids() -> list[str]:
    """마을 운영자가 있는 마을 번호만. 카카오 사용자 ID는 읽지 않는다."""
    client = get_supabase_client()
    if client:
        result = (
            client.table("operators")
            .select("village_id")
            .eq("role", "village")
            .eq("is_active", True)
            .execute()
        )
        ids = [row.get("village_id") for row in (result.data or []) if row.get("village_id")]
    else:
        ids = [
            operator.get("village_id")
            for operator in _operators
            if _is_village_role(operator) and operator.get("is_active", True) and operator.get("village_id")
        ]
    return sorted({str(village_id) for village_id in ids})


def list_operators_for_village(village_id: str) -> list[dict]:
    client = get_supabase_client()
    if client:
        result = client.table("operators").select("*").eq("village_id", village_id).execute()
        return result.data or []
    return [operator for operator in _operators if operator.get("village_id") == village_id]


def get_village_operator(village_id: str) -> dict | None:
    for operator in list_operators_for_village(village_id):
        if _is_village_role(operator):
            return operator
    return None


def get_program_operator(village_id: str, program_key: str) -> dict | None:
    for operator in list_operators_for_village(village_id):
        if operator.get("role") == "program" and operator.get("program_key") == program_key:
            return operator
    return None


def get_operator_by_village_id(village_id: str) -> dict | None:
    """마을 운영자 한 명. 체험 담당은 포함하지 않는다."""
    return get_village_operator(village_id)


def set_operator_login_id(village_id: str, login_id: str) -> dict | None:
    """웹 로그인만 바꾼다. kakao_user_id는 그대로 둔다."""
    client = get_supabase_client()
    if client:
        result = (
            client.table("operators")
            .update({"login_id": login_id})
            .eq("village_id", village_id)
            .eq("role", "village")
            .execute()
        )
        return result.data[0] if result.data else None
    for operator in _operators:
        if operator.get("village_id") == village_id and _is_village_role(operator):
            operator["login_id"] = login_id
            return dict(operator)
    return None


def insert_operator(row: dict) -> dict:
    global _operators
    client = get_supabase_client()
    saved = dict(row)
    saved.setdefault("role", "village")
    if client:
        result = client.table("operators").insert(saved).execute()
        return result.data[0] if result.data else saved
    if "operator_id" not in saved:
        saved["operator_id"] = max((op.get("operator_id") or 0) for op in _operators) + 1
    _operators.append(saved)
    return saved


def delete_operator_by_kakao_id(kakao_user_id: str) -> None:
    global _operators
    client = get_supabase_client()
    if client:
        client.table("operators").delete().eq("kakao_user_id", kakao_user_id).execute()
        return
    _operators = [op for op in _operators if op.get("kakao_user_id") != kakao_user_id]


def get_operator_by_login_id(login_id: str) -> dict | None:
    client = get_supabase_client()
    if client:
        result = (
            client.table("operators")
            .select("*")
            .eq("login_id", login_id)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    for op in _operators:
        if op.get("login_id") == login_id and op.get("is_active"):
            return op
    return None


def reset_booking_store() -> None:
    """테스트용 예약·후기 인메모리 초기화."""
    global _bookings, _reviews, _booking_id_counter, _review_id_counter
    _bookings = []
    _reviews = []
    _booking_id_counter = 1
    _review_id_counter = 1


def reset_content_store() -> None:
    """테스트용 운영 콘텐츠 인메모리 초기화."""
    global _contents, _content_id_counter
    _contents = []
    _content_id_counter = 1


def reset_program_store() -> None:
    """테스트용 프로그램 운영 여부 초기화. 마을 동기화는 이 저장소를 비우지 않는다."""
    global _program_status
    _program_status = []


def reset_share_store() -> None:
    """테스트용 체험 글·달력 초기화."""
    global _program_notes, _calendar, _calendar_id_counter
    _program_notes = []
    _calendar = []
    _calendar_id_counter = 1


def reset_memory_store() -> None:
    """테스트용 인메모리 저장소 초기화."""
    global _client, _villages_cache, _sync_logs
    _client = None
    _clear_recommend_cache()
    _villages_cache = []
    _sync_logs = []
    reset_booking_store()
    reset_content_store()
    reset_program_store()
    reset_share_store()


def delete_bookings_for_village(village_id: str) -> None:
    global _bookings
    client = get_supabase_client()
    if client:
        client.table("bookings").delete().eq("village_id", village_id).execute()
        return
    _bookings = [row for row in _bookings if row.get("village_id") != village_id]


def _clear_operator_link(client, table: str, column: str, village_id: str) -> None:
    try:
        client.table(table).update({column: None}).eq("village_id", village_id).execute()
    except Exception as exc:
        if _missing_share_table(exc):
            return
        raise


def delete_operators_for_village(village_id: str) -> None:
    global _operators
    client = get_supabase_client()
    if client:
        client.table("contents").update({"operator_id": None}).eq("village_id", village_id).execute()
        _clear_operator_link(client, "program_notes", "updated_by", village_id)
        _clear_operator_link(client, "experience_calendar", "created_by", village_id)
        client.table("operators").delete().eq("village_id", village_id).execute()
        return
    for row in _contents:
        if row.get("village_id") == village_id:
            row["operator_id"] = None
    for row in _program_notes:
        if row.get("village_id") == village_id:
            row["updated_by"] = None
    for row in _calendar:
        if row.get("village_id") == village_id:
            row["created_by"] = None
    _operators = [row for row in _operators if row.get("village_id") != village_id]


def delete_reviews_for_village(village_id: str) -> None:
    global _reviews
    client = get_supabase_client()
    if client:
        client.table("reviews").delete().eq("village_id", village_id).execute()
        return
    _reviews = [row for row in _reviews if row.get("village_id") != village_id]


def delete_contents_for_village(village_id: str) -> None:
    global _contents
    client = get_supabase_client()
    if client:
        client.table("contents").delete().eq("village_id", village_id).execute()
        return
    _contents = [row for row in _contents if row.get("village_id") != village_id]


def delete_program_notes_for_village(village_id: str) -> None:
    global _program_notes
    client = get_supabase_client()
    if client:
        try:
            client.table("program_notes").delete().eq("village_id", village_id).execute()
        except Exception as exc:
            if _missing_share_table(exc):
                return
            raise
        return
    _program_notes = [row for row in _program_notes if row.get("village_id") != village_id]


def insert_booking(row: dict) -> dict:
    global _booking_id_counter
    client = get_supabase_client()
    if client:
        result = client.table("bookings").insert(row).execute()
        if result.data:
            return result.data[0]
        return dict(row)
    saved = dict(row)
    saved["booking_id"] = _booking_id_counter
    _booking_id_counter += 1
    _bookings.append(saved)
    return dict(saved)


def list_bookings(
    *,
    village_id: str | None = None,
    customer_kakao_id: str | None = None,
    booking_id: int | None = None,
) -> list[dict]:
    """필터가 없으면 빈 목록. 마을 또는 고객 또는 예약번호로만 읽는다."""
    if village_id is None and customer_kakao_id is None and booking_id is None:
        return []
    client = get_supabase_client()
    if client:
        query = client.table("bookings").select("*")
        if village_id is not None:
            query = query.eq("village_id", village_id)
        if customer_kakao_id is not None:
            query = query.eq("customer_kakao_id", customer_kakao_id)
        if booking_id is not None:
            query = query.eq("booking_id", booking_id)
        result = query.order("booking_id").execute()
        return result.data or []
    rows = _bookings
    if village_id is not None:
        rows = [row for row in rows if row.get("village_id") == village_id]
    if customer_kakao_id is not None:
        rows = [row for row in rows if row.get("customer_kakao_id") == customer_kakao_id]
    if booking_id is not None:
        rows = [row for row in rows if row.get("booking_id") == booking_id]
    return [dict(row) for row in sorted(rows, key=lambda row: row.get("booking_id") or 0)]


def save_booking_status(booking_id: int, status: str) -> dict | None:
    client = get_supabase_client()
    if client:
        result = (
            client.table("bookings").update({"status": status}).eq("booking_id", booking_id).execute()
        )
        if not result.data:
            return None
        return result.data[0]
    for row in _bookings:
        if row.get("booking_id") == booking_id:
            row["status"] = status
            return dict(row)
    return None


def insert_review(row: dict) -> dict:
    global _review_id_counter
    client = get_supabase_client()
    if client:
        result = client.table("reviews").insert(row).execute()
        if result.data:
            return result.data[0]
        return dict(row)
    saved = dict(row)
    saved["review_id"] = _review_id_counter
    _review_id_counter += 1
    _reviews.append(saved)
    return dict(saved)


def insert_content(row: dict) -> dict:
    global _content_id_counter
    client = get_supabase_client()
    if client:
        result = client.table("contents").insert(row).execute()
        if result.data:
            return result.data[0]
        return dict(row)
    saved = dict(row)
    saved["content_id"] = _content_id_counter
    _content_id_counter += 1
    _contents.append(saved)
    return dict(saved)


def set_village_public_contents(village_id: str, content_ids: list[int]) -> list[dict]:
    """그 마을의 공개를 content_ids만 남긴다."""
    chosen = {int(content_id) for content_id in content_ids}
    client = get_supabase_client()
    if client:
        client.table("contents").update({"is_public": False}).eq("village_id", village_id).execute()
        if chosen:
            (
                client.table("contents")
                .update({"is_public": True})
                .eq("village_id", village_id)
                .in_("content_id", list(chosen))
                .execute()
            )
        return list_contents(village_id=village_id)
    for row in _contents:
        if row.get("village_id") == village_id:
            row["is_public"] = int(row.get("content_id") or 0) in chosen
    return list_contents(village_id=village_id)


def list_public_contents() -> list[dict]:
    """관광객 목록용. 공개된 소개글·SNS만 돌려준다."""
    fields = ("village_id", "content_type", "body", "photo_url", "content_id")
    client = get_supabase_client()
    if client:
        result = (
            client.table("contents")
            .select(",".join(fields))
            .eq("is_public", True)
            .in_("content_type", ["소개글", "SNS홍보문구"])
            .order("content_id")
            .execute()
        )
        return result.data or []
    rows = [
        row
        for row in _contents
        if row.get("is_public") and row.get("content_type") in {"소개글", "SNS홍보문구"}
    ]
    slim = []
    for row in sorted(rows, key=lambda item: item.get("content_id") or 0):
        slim.append({field: row.get(field) for field in fields})
    return slim


def _missing_program_table(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    if code == "PGRST205":
        return True
    message = str(exc)
    return "village_program_status" in message and "schema cache" in message


def _missing_share_table(exc: Exception) -> bool:
    message = str(exc)
    if "schema cache" not in message and getattr(exc, "code", None) != "PGRST205":
        return False
    return "program_notes" in message or "experience_calendar" in message or getattr(exc, "code", None) == "PGRST205"


def list_program_status(village_id: str) -> list[dict]:
    if not village_id:
        return []
    grouped = list_program_status_map([village_id])
    return grouped.get(village_id, [])


def list_program_status_map(village_ids: list[str]) -> dict[str, list[dict]]:
    ids = [village_id for village_id in village_ids if village_id]
    if not ids:
        return {}
    client = get_supabase_client()
    if client:
        try:
            result = (
                client.table("village_program_status")
                .select("*")
                .in_("village_id", ids)
                .execute()
            )
        except Exception as exc:
            if _missing_program_table(exc):
                return {}
            raise
        grouped: dict[str, list[dict]] = {}
        for row in result.data or []:
            grouped.setdefault(str(row.get("village_id") or ""), []).append(row)
        return grouped
    grouped = {}
    for row in _program_status:
        village_id = str(row.get("village_id") or "")
        if village_id in ids:
            grouped.setdefault(village_id, []).append(dict(row))
    return grouped


def save_program_status(
    village_id: str, program_key: str, label: str, is_operating: bool
) -> None:
    """운영 여부만 저장한다. villages_cache 동기화 upsert와 별도다."""
    from datetime import datetime, timezone

    row = {
        "village_id": village_id,
        "program_key": program_key,
        "label": label,
        "is_operating": is_operating,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    client = get_supabase_client()
    if client:
        try:
            client.table("village_program_status").upsert(row).execute()
        except Exception as exc:
            if _missing_program_table(exc):
                raise RuntimeError("프로그램 운영 여부 저장소가 아직 없습니다.") from exc
            raise
        return
    for existing in _program_status:
        if existing.get("village_id") == village_id and existing.get("program_key") == program_key:
            existing.update(row)
            return
    _program_status.append(row)


def list_contents(*, village_id: str | None = None) -> list[dict]:
    if village_id is None:
        return []
    client = get_supabase_client()
    if client:
        result = (
            client.table("contents")
            .select("*")
            .eq("village_id", village_id)
            .order("content_id")
            .execute()
        )
        return result.data or []
    rows = [row for row in _contents if row.get("village_id") == village_id]
    return [dict(row) for row in sorted(rows, key=lambda row: row.get("content_id") or 0)]


def list_reviews(*, village_id: str | None = None) -> list[dict]:
    if village_id is None:
        return []
    client = get_supabase_client()
    if client:
        result = (
            client.table("reviews").select("*").eq("village_id", village_id).order("review_id").execute()
        )
        return result.data or []
    rows = [row for row in _reviews if row.get("village_id") == village_id]
    return [dict(row) for row in sorted(rows, key=lambda row: row.get("review_id") or 0)]


def upsert_program_note(row: dict) -> dict:
    client = get_supabase_client()
    if client:
        try:
            result = client.table("program_notes").upsert(row).execute()
        except Exception as exc:
            if _missing_share_table(exc):
                raise RuntimeError("체험 글 저장소가 아직 없습니다.") from exc
            raise
        return result.data[0] if result.data else row
    for existing in _program_notes:
        if existing.get("village_id") == row["village_id"] and existing.get("program_key") == row["program_key"]:
            existing.update(row)
            return dict(existing)
    _program_notes.append(dict(row))
    return dict(row)


def list_program_notes_for_village(village_id: str) -> list[dict]:
    if not village_id:
        return []
    client = get_supabase_client()
    if client:
        try:
            result = (
                client.table("program_notes").select("*").eq("village_id", village_id).execute()
            )
        except Exception as exc:
            if _missing_share_table(exc):
                return []
            raise
        rows = result.data or []
    else:
        rows = [row for row in _program_notes if row.get("village_id") == village_id]
    return [dict(row) for row in sorted(rows, key=lambda row: str(row.get("label") or ""))]


def upsert_calendar_entry(row: dict) -> dict:
    global _calendar_id_counter
    client = get_supabase_client()
    if client:
        try:
            result = (
                client.table("experience_calendar")
                .upsert(row, on_conflict="village_id,program_key,visit_date,group_name")
                .execute()
            )
        except Exception as exc:
            if _missing_share_table(exc):
                raise RuntimeError("체험 달력 저장소가 아직 없습니다.") from exc
            raise
        return result.data[0] if result.data else row
    for existing in _calendar:
        if (
            existing.get("village_id") == row["village_id"]
            and existing.get("program_key") == row["program_key"]
            and existing.get("visit_date") == row["visit_date"]
            and existing.get("group_name") == row.get("group_name")
        ):
            existing.update(row)
            return dict(existing)
    saved = dict(row)
    saved["calendar_id"] = _calendar_id_counter
    _calendar_id_counter += 1
    _calendar.append(saved)
    return dict(saved)


def delete_calendar_entry_row(
    village_id: str, program_key: str, visit_date: str, group_name: str
) -> None:
    global _calendar
    client = get_supabase_client()
    if client:
        (
            client.table("experience_calendar")
            .delete()
            .eq("village_id", village_id)
            .eq("program_key", program_key)
            .eq("visit_date", visit_date)
            .eq("group_name", group_name)
            .execute()
        )
        return
    _calendar = [
        row
        for row in _calendar
        if not (
            row.get("village_id") == village_id
            and row.get("program_key") == program_key
            and row.get("visit_date") == visit_date
            and row.get("group_name") == group_name
        )
    ]


def delete_calendar_for_village(village_id: str) -> None:
    global _calendar
    client = get_supabase_client()
    if client:
        client.table("experience_calendar").delete().eq("village_id", village_id).execute()
        return
    _calendar = [row for row in _calendar if row.get("village_id") != village_id]


def list_calendar_for_village(village_id: str) -> list[dict]:
    if not village_id:
        return []
    client = get_supabase_client()
    if client:
        try:
            result = (
                client.table("experience_calendar").select("*").eq("village_id", village_id).execute()
            )
        except Exception as exc:
            if _missing_share_table(exc):
                return []
            raise
        rows = result.data or []
    else:
        rows = [row for row in _calendar if row.get("village_id") == village_id]
    return [
        dict(row)
        for row in sorted(
            rows,
            key=lambda row: (
                str(row.get("visit_date") or ""),
                str(row.get("label") or ""),
                str(row.get("group_name") or ""),
            ),
        )
    ]
