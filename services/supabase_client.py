"""Supabase 클라이언트 및 인메모리 폴백 (로컬/테스트용)."""

import os
from typing import Any

_villages_cache: list[dict] = []
_sync_logs: list[dict] = []
_operators: list[dict] = [
    {
        "operator_id": 1,
        "village_id": "V001",
        "kakao_user_id": "kakao_owner_v001",
        "login_id": "owner_v001",
        "operator_name": "V001 운영자",
        "registered_at": "2026-09-01T00:00:00+00:00",
        "is_active": True,
    },
    {
        "operator_id": 2,
        "village_id": "V002",
        "kakao_user_id": "kakao_owner_v002",
        "login_id": "owner_v002",
        "operator_name": "V002 운영자",
        "registered_at": "2026-09-01T00:00:00+00:00",
        "is_active": True,
    },
    {
        "operator_id": 3,
        "village_id": "V001",
        "kakao_user_id": "owner_test",
        "login_id": "owner_test",
        "operator_name": "테스트 운영자",
        "registered_at": "2026-09-01T00:00:00+00:00",
        "is_active": True,
    },
]


def _use_supabase() -> bool:
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


def get_supabase_client():
    if not _use_supabase():
        return None
    from supabase import create_client

    return create_client(os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""))


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
        return
    by_id = {v["village_id"]: v for v in _villages_cache}
    for row in payload:
        existing = by_id.get(row["village_id"], {})
        merged = {**existing, **row}
        if "registration_code" in existing:
            merged["registration_code"] = existing["registration_code"]
        by_id[row["village_id"]] = merged
    _villages_cache = list(by_id.values())


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
    villages = list_villages()
    for village in villages:
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


def get_operator_by_village_id(village_id: str) -> dict | None:
    client = get_supabase_client()
    if client:
        result = (
            client.table("operators")
            .select("*")
            .eq("village_id", village_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None
    for operator in _operators:
        if operator.get("village_id") == village_id:
            return operator
    return None


def insert_operator(row: dict) -> dict:
    global _operators
    client = get_supabase_client()
    if client:
        result = client.table("operators").insert(row).execute()
        return result.data[0] if result.data else row
    saved = dict(row)
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


def reset_memory_store() -> None:
    """테스트용 인메모리 저장소 초기화."""
    global _villages_cache, _sync_logs
    _villages_cache = []
    _sync_logs = []
