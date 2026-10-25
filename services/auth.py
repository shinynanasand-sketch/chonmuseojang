"""운영자 인증 및 테넌트 필터 헬퍼 (FR-15)."""

from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException

from services import supabase_client
from services.village_programs import program_key, program_labels


def get_operator_by_kakao_id(kakao_user_id: str) -> dict | None:
    return supabase_client.get_operator_by_kakao_id(kakao_user_id)


def resolve_kakao_role(user_id: str) -> dict:
    """user.id로 operators.kakao_user_id를 대조한다."""
    row = get_operator_by_kakao_id(user_id)
    if not row:
        return {"mode": "tourist", "village_id": None, "role": None, "program_key": None}
    return {
        "mode": "operator",
        "village_id": row["village_id"],
        "role": row.get("role") or "village",
        "program_key": row.get("program_key"),
    }


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
    """마을명과 코드가 맞을 때만 저장한다. 첫 사람은 마을 운영자, 다음은 체험 담당이다."""
    parsed = _parse_registration(utterance)
    if not parsed.get("ok"):
        return {"ok": False, "reason": parsed["reason"]}
    return _register_matches(user_id, parsed["matches"], parsed["program"])


def register_operator_with_ids(
    user_id: str, village_id: str, code: str, program_label: str = ""
) -> dict:
    """대표값 village_id와 registration_code가 그 행과 맞을 때만 저장한다."""
    row = supabase_client.get_village_by_id(village_id)
    if row is None:
        return {"ok": False, "reason": "village_not_found"}
    if str(row.get("registration_code") or "").strip() != code.strip():
        return {"ok": False, "reason": "code_mismatch"}
    return _register_matches(user_id, [row], program_label.strip())


def _register_matches(user_id: str, matches: list[dict], program: str) -> dict:
    if supabase_client.get_operator_by_kakao_id(user_id):
        return {"ok": False, "reason": "already_registered"}
    village_operator = None
    for row in matches:
        found = supabase_client.get_village_operator(row["village_id"])
        if found:
            village_operator = found
            break
    if not program:
        if village_operator:
            return {"ok": False, "reason": "already_registered"}
        village = _preferred_village(matches)
        supabase_client.insert_operator(
            {
                "kakao_user_id": user_id,
                "village_id": village["village_id"],
                "role": "village",
                "operator_name": str(village.get("village_name") or village["village_id"]) + " 운영자",
                "registered_at": datetime.now(timezone.utc).isoformat(),
                "is_active": True,
            }
        )
        return {"ok": True, "village_id": village["village_id"]}
    if village_operator is None:
        return {"ok": False, "reason": "village_operator_required"}
    target = next(row for row in matches if row["village_id"] == village_operator["village_id"])
    normalized = " ".join(program.split())
    canonical = next(
        (label for label in program_labels(target) if " ".join(label.split()) == normalized),
        "",
    )
    if not canonical:
        return {"ok": False, "reason": "program_not_found"}
    key = program_key(canonical)
    if supabase_client.get_program_operator(target["village_id"], key):
        return {"ok": False, "reason": "program_taken"}
    supabase_client.insert_operator(
        {
            "kakao_user_id": user_id,
            "village_id": target["village_id"],
            "role": "program",
            "program_key": key,
            "operator_name": f"{target.get('village_name') or target['village_id']} {canonical} 담당",
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "is_active": True,
        }
    )
    return {"ok": True, "village_id": target["village_id"], "role": "program"}


def _parse_registration(utterance: str) -> dict:
    parts = utterance.split()
    if parts and parts[0] == "등록":
        parts = parts[1:]
    if len(parts) < 2:
        return {"ok": False, "reason": "bad_format"}
    saw_code_mismatch = False
    for index in range(1, len(parts)):
        spoken = " ".join(parts[:index])
        code = parts[index]
        program = " ".join(parts[index + 1 :]).strip()
        named = _named_villages(spoken)
        if named is None:
            return {"ok": False, "reason": "village_not_found"}
        if not named:
            continue
        matched = [
            row
            for row in named
            if str(row.get("registration_code") or "").strip() == code.strip()
        ]
        if not matched:
            saw_code_mismatch = True
            continue
        return {"ok": True, "matches": matched, "program": program}
    if saw_code_mismatch:
        return {"ok": False, "reason": "code_mismatch"}
    return {"ok": False, "reason": "village_not_found"}


def _one_sigungu(rows: list[dict]) -> list[dict] | None:
    """같은 마을명이 여러 시군이면 None이다."""
    sigungus = {str(row.get("sigungu") or "").strip() for row in rows}
    if len(sigungus) > 1:
        return None
    return rows


def _named_villages(spoken: str) -> list[dict] | None:
    """마을명 일치 한 번, 없으면 시군과 마을명 일치 한 번. 전체 목록은 읽지 않는다."""
    exact = _one_sigungu(supabase_client.list_villages_by_name(spoken))
    if exact is None or exact:
        return exact
    if " " not in spoken:
        return []
    sigungu, name = spoken.split(" ", 1)
    return supabase_client.list_villages_by_name(name, sigungu=sigungu)


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


async def require_village_operator(
    current_operator: dict = Depends(get_current_operator),
) -> dict:
    """예약·후기·홍보 웹은 마을 운영자만 연다."""
    if (current_operator.get("role") or "village") != "village":
        raise HTTPException(
            status_code=403,
            detail="마을 운영자만 예약·후기·홍보를 다룰 수 있습니다.",
        )
    return current_operator


def require_village_access(current_operator: dict, village_id: str) -> None:
    """타 마을 접근 시 403."""
    if not assert_operator_owns_village(current_operator, village_id):
        raise HTTPException(status_code=403, detail="해당 마을에 대한 접근 권한이 없습니다.")
