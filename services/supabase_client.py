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
        "is_active": True,
        "display_name": "V001 운영자",
    },
    {
        "operator_id": 2,
        "village_id": "V002",
        "kakao_user_id": "kakao_owner_v002",
        "login_id": "owner_v002",
        "is_active": True,
        "display_name": "V002 운영자",
    },
    {
        "operator_id": 3,
        "village_id": "V001",
        "kakao_user_id": "owner_test",
        "login_id": "owner_test",
        "is_active": True,
        "display_name": "테스트 운영자",
    },
]


def _use_supabase() -> bool:
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY"))


def get_supabase_client():
    if not _use_supabase():
        return None
    from supabase import create_client

    return create_client(os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""))


def upsert_villages(rows: list[dict]) -> None:
    global _villages_cache
    client = get_supabase_client()
    if client:
        client.table("villages_cache").upsert(rows).execute()
        return
    by_id = {v["village_id"]: v for v in _villages_cache}
    for row in rows:
        by_id[row["village_id"]] = row
    _villages_cache = list(by_id.values())


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
