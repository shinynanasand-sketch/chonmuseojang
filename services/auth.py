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
    """발화 `등록 [마을명] [코드]`가 registration_code와 맞을 때만 operators에 저장한다."""
    parts = utterance.split()
    if len(parts) < 3 or parts[0] != "등록":
        return {"ok": False, "reason": "bad_format"}
    code = parts[-1]
    village_name = " ".join(parts[1:-1])
    matches = [
        row
        for row in supabase_client.list_villages()
        if row.get("village_name") == village_name
    ]
    if len(matches) != 1:
        return {"ok": False, "reason": "village_not_found"}
    village = matches[0]
    if village.get("registration_code") != code:
        return {"ok": False, "reason": "code_mismatch"}
    if supabase_client.get_operator_by_village_id(village["village_id"]):
        return {"ok": False, "reason": "already_registered"}
    supabase_client.insert_operator(
        {
            "kakao_user_id": user_id,
            "village_id": village["village_id"],
            "operator_name": village_name + " 운영자",
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "is_active": True,
        }
    )
    return {"ok": True, "village_id": village["village_id"]}


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
