"""운영자 인증 및 테넌트 필터 헬퍼 (FR-15)."""

from datetime import datetime, timezone

from fastapi import Header, HTTPException

from services import supabase_client


def get_operator_by_kakao_id(kakao_user_id: str) -> dict | None:
    return supabase_client.get_operator_by_kakao_id(kakao_user_id)


def resolve_kakao_role(user_id: str) -> dict:
    """user.id로 operators.kakao_user_id를 대조한다."""
    row = get_operator_by_kakao_id(user_id)
    if not row:
        return {"mode": "tourist", "village_id": None}
    return {"mode": "operator", "village_id": row["village_id"]}


def scoped_village_id(user_id: str) -> str:
    """카카오 운영자 쿼리에 붙일 village_id. 관광객이면 운영자 쿼리를 실행하지 않는다."""
    role = resolve_kakao_role(user_id)
    if role["mode"] != "operator":
        raise PermissionError("operator required")
    return role["village_id"]


def scoped_village_id_for_session(operator_id: int) -> str:
    """웹 세션의 operator_id로 담당 village_id를 반환한다."""
    row = supabase_client.get_operator_by_id(operator_id)
    if not row:
        raise PermissionError("operator required")
    return row["village_id"]


def assert_operator_owns_village(current_operator: dict, village_id: str) -> bool:
    """운영자가 해당 마을에 접근 권한이 있는지 확인한다."""
    return current_operator.get("village_id") == village_id


def register_operator(user_id: str, utterance: str) -> dict:
    """마을명과 코드가 registration_code와 맞을 때만 operators에 저장한다."""
    parts = utterance.split()
    if parts and parts[0] == "등록":
        parts = parts[1:]
    if len(parts) < 2:
        return {"ok": False, "reason": "bad_format"}
    code = parts[-1]
    spoken = " ".join(parts[:-1])
    matches = _villages_for_registration(spoken, code)
    if matches is None:
        return {"ok": False, "reason": "village_not_found"}
    if not matches:
        return {"ok": False, "reason": "code_mismatch"}
    village = _preferred_village(matches)
    if any(
        supabase_client.get_operator_by_village_id(row["village_id"]) for row in matches
    ):
        return {"ok": False, "reason": "already_registered"}
    supabase_client.insert_operator(
        {
            "kakao_user_id": user_id,
            "village_id": village["village_id"],
            "operator_name": str(village.get("village_name") or spoken) + " 운영자",
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "is_active": True,
        }
    )
    return {"ok": True, "village_id": village["village_id"]}


def register_operator_with_ids(user_id: str, village_id: str, code: str) -> dict:
    """대표값 village_id와 registration_code가 그 행과 맞을 때만 저장한다."""
    row = supabase_client.get_village_by_id(village_id)
    if row is None:
        return {"ok": False, "reason": "village_not_found"}
    if str(row.get("registration_code") or "").strip() != code.strip():
        return {"ok": False, "reason": "code_mismatch"}
    if supabase_client.get_operator_by_village_id(village_id):
        return {"ok": False, "reason": "already_registered"}
    supabase_client.insert_operator(
        {
            "kakao_user_id": user_id,
            "village_id": row["village_id"],
            "operator_name": str(row.get("village_name") or village_id) + " 운영자",
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "is_active": True,
        }
    )
    return {"ok": True, "village_id": row["village_id"]}


def _villages_for_registration(spoken: str, code: str) -> list[dict] | None:
    """같은 코드의 시도 중복 행은 한 마을이다. 시군이 다르면 시군구가 발화에 있어야 한다."""
    rows = supabase_client.list_villages()
    exact = [row for row in rows if str(row.get("village_name") or "").strip() == spoken]
    if exact:
        sigungus = {str(row.get("sigungu") or "").strip() for row in exact}
        if len(sigungus) > 1:
            return None
        candidates = exact
    else:
        candidates = [
            row
            for row in rows
            if f"{str(row.get('sigungu') or '').strip()} {str(row.get('village_name') or '').strip()}".strip()
            == spoken
        ]
        if not candidates:
            return None
    return [
        row
        for row in candidates
        if str(row.get("registration_code") or "").strip() == code
    ]


def _preferred_village(rows: list[dict]) -> dict:
    chosen = rows[0]

    def rank(village: dict) -> int:
        text = f"{village.get('sido') or ''} {village.get('address') or ''}"
        if "전남광주통합특별시" in text:
            return 0
        if "광주특별시" in text:
            return 1
        return 2

    for row in rows[1:]:
        if rank(row) < rank(chosen):
            chosen = row
    return chosen


async def get_current_operator(
    authorization: str | None = Header(default=None),
) -> dict:
    """웹 세션은 login_id 또는 operator_id만 받는다. 카카오 user.id는 쓰지 않는다."""
    operator = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        if token.isdigit():
            operator = supabase_client.get_operator_by_id(int(token))
        else:
            operator = supabase_client.get_operator_by_login_id(token)

    if not operator:
        raise HTTPException(status_code=401, detail="운영자 인증이 필요합니다.")
    operator = dict(operator)
    operator["village_id"] = scoped_village_id_for_session(operator["operator_id"])
    return operator


def require_village_access(current_operator: dict, village_id: str) -> None:
    """타 마을 접근 시 403."""
    if not assert_operator_owns_village(current_operator, village_id):
        raise HTTPException(status_code=403, detail="해당 마을에 대한 접근 권한이 없습니다.")
