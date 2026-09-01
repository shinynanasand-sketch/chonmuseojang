"""운영자 인증 및 테넌트 필터 헬퍼 (FR-15)."""

from fastapi import Header, HTTPException

from services import supabase_client


def scoped_village_id(current_operator: dict) -> str:
    """운영자 쿼리에 사용할 village_id. 요청 파라미터는 신뢰하지 않는다."""
    return current_operator["village_id"]


def assert_operator_owns_village(current_operator: dict, village_id: str) -> bool:
    """운영자가 해당 마을에 접근 권한이 있는지 확인한다."""
    return scoped_village_id(current_operator) == village_id


def get_operator_by_kakao_id(kakao_user_id: str) -> dict | None:
    return supabase_client.get_operator_by_kakao_id(kakao_user_id)


async def get_current_operator(
    authorization: str | None = Header(default=None),
    x_operator_kakao_id: str | None = Header(default=None, alias="X-Operator-Kakao-Id"),
) -> dict:
    """Bearer 토큰(카카오 ID 또는 login_id)으로 운영자를 식별한다."""
    operator = None
    if x_operator_kakao_id:
        operator = get_operator_by_kakao_id(x_operator_kakao_id)
    elif authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        operator = get_operator_by_kakao_id(token) or supabase_client.get_operator_by_login_id(token)

    if not operator:
        raise HTTPException(status_code=401, detail="운영자 인증이 필요합니다.")
    return operator


def require_village_access(current_operator: dict, village_id: str) -> None:
    """타 마을 접근 시 403."""
    if not assert_operator_owns_village(current_operator, village_id):
        raise HTTPException(status_code=403, detail="해당 마을에 대한 접근 권한이 없습니다.")
