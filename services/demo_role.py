"""발표 모드에서만 쓰는 시연 역할.

저장된 운영자 등록은 바꾸지 않는다. 고른 역할은 그 계정 위에만 얹는다.
주소에는 세션 번호만 두고, 카카오 사용자 ID는 넣지 않는다.
"""

import hashlib
import hmac
import os
import secrets
import time
from datetime import datetime, timezone

from services.demo_data import DEMO_STAFF_KAKAO_ID, DEMO_STAFF_NAME, DEMO_VILLAGE_ID

_PERSONAS = {"guest", "village", "program"}
_FALLBACK_SECRET = secrets.token_hex(16)
_sessions: dict[str, dict] = {}
_by_user: dict[str, str] = {}
_marks: set[int] = set()
_table_ready = {"sessions": None, "marks": None}


def reset_demo_roles() -> None:
    """테스트가 역할과 심사 예약 표시를 비운다."""
    _sessions.clear()
    _by_user.clear()
    _marks.clear()
    _table_ready["sessions"] = None
    _table_ready["marks"] = None


def _presentation_on() -> bool:
    from config import presentation_enabled

    return presentation_enabled()


def _secret() -> str:
    from config import CRON_SECRET

    return CRON_SECRET or os.getenv("CRON_SECRET", "") or _FALLBACK_SECRET


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _remember(row: dict) -> dict:
    stored = dict(row)
    session_id = str(stored.get("session_id") or "")
    user_id = str(stored.get("kakao_user_id") or "")
    if session_id:
        _sessions[session_id] = stored
    if user_id and session_id:
        _by_user[user_id] = session_id
    return stored


def _persist_session(row: dict) -> None:
    if _table_ready["sessions"] is False:
        return
    from services.supabase_client import get_supabase_client

    client = get_supabase_client()
    if not client:
        return
    try:
        client.table("demo_sessions").upsert(dict(row), on_conflict="session_id").execute()
    except Exception:
        _table_ready["sessions"] = False
        return
    _table_ready["sessions"] = True


def _load_session(session_id: str) -> dict | None:
    found = _sessions.get(session_id)
    if found:
        return found
    if _table_ready["sessions"] is False:
        return None
    from services.supabase_client import get_supabase_client

    client = get_supabase_client()
    if not client:
        return None
    try:
        result = (
            client.table("demo_sessions").select("*").eq("session_id", session_id).limit(1).execute()
        )
    except Exception:
        _table_ready["sessions"] = False
        return None
    _table_ready["sessions"] = True
    if not result.data:
        return None
    return _remember(result.data[0])


def _load_user(user_id: str) -> dict | None:
    session_id = _by_user.get(user_id)
    if session_id and session_id in _sessions:
        return _sessions[session_id]
    if _table_ready["sessions"] is False:
        return None
    from services.supabase_client import get_supabase_client

    client = get_supabase_client()
    if not client:
        return None
    try:
        result = (
            client.table("demo_sessions")
            .select("*")
            .eq("kakao_user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception:
        _table_ready["sessions"] = False
        return None
    _table_ready["sessions"] = True
    if not result.data:
        return None
    return _remember(result.data[0])


def _village_id_for(user_id: str) -> str:
    from services.supabase_client import get_operator_by_kakao_id

    row = get_operator_by_kakao_id(user_id)
    if row and row.get("village_id"):
        return str(row["village_id"])
    return DEMO_VILLAGE_ID


def _ensure_session(user_id: str) -> dict:
    found = _load_user(user_id)
    if found:
        return found
    row = {
        "session_id": secrets.token_hex(16),
        "kakao_user_id": user_id,
        "persona": "",
        "village_id": _village_id_for(user_id),
        "updated_at": _now(),
    }
    _remember(row)
    _persist_session(row)
    return row


def role_page_url(user_id: str) -> str:
    """시연 역할 화면. 토큰에는 세션 번호와 만료만 있다."""
    session = _ensure_session(user_id)
    expires = int(time.time()) + 14 * 24 * 60 * 60
    body = f"{session['session_id']}.{expires}"
    signature = hmac.new(_secret().encode(), body.encode(), hashlib.sha256).hexdigest()
    base = os.getenv("PUBLIC_BASE_URL", "https://chonmuseojang.vercel.app").rstrip("/")
    return f"{base}/demo/role/{body}.{signature}"


def role_quick_reply(user_id: str) -> dict | None:
    """발표 모드의 역할 화면 버튼. 바로연결에 넣으면 카카오가 칩 전체를 버린다."""
    if not user_id or not _presentation_on():
        return None
    return {"label": "시연 역할", "action": "webLink", "webLinkUrl": role_page_url(user_id)}


_ROLE_LABELS = {"guest": "체험객", "village": "사무장", "program": "체험 담당"}
_OPERATOR_BUTTONS = {"예약 현황 조회", "체험 달력 조회", "체험 글 조회", "홍보 사진", "체험 글 저장"}


def role_card_description(user_id: str) -> str:
    """고른 역할이 있으면 카드에 그 이름을 적는다."""
    label = _ROLE_LABELS.get(persona_of(user_id) or "")
    if not label:
        return "체험객, 사무장, 체험 담당을 바꿉니다."
    return f"지금 역할은 {label}입니다."


def chosen_role_reply(user_id: str, utterance: str) -> str | None:
    """다른 역할의 버튼이면 고른 역할 문장. 고르지 않았으면 기존 답을 둔다."""
    persona = persona_of(user_id)
    if persona not in _PERSONAS:
        return None
    text = " ".join((utterance or "").split())
    if persona in {"village", "program"} and _tourist_button(text):
        return persona_message(user_id, persona)
    if persona == "guest" and _operator_button(text):
        return "지금은 체험객입니다. 예약하기와 내 예약을 씁니다."
    return None


def _tourist_button(text: str) -> bool:
    if text in {"예약하기", "내 예약", "후기 보기"}:
        return True
    return text.startswith("예약하기 ") or text.startswith("후기 보기 ")


def _operator_button(text: str) -> bool:
    if text in _OPERATOR_BUTTONS:
        return True
    from services.booking import is_week_status_utterance

    return is_week_status_utterance(text)


def session_from_token(token: str) -> dict | None:
    if not _presentation_on():
        return None
    parts = (token or "").split(".")
    if len(parts) != 3:
        return None
    session_id, expires, signature = parts
    if not session_id or not expires.isdigit():
        return None
    try:
        if int(expires) < int(time.time()):
            return None
    except ValueError:
        return None
    body = f"{session_id}.{expires}"
    expected = hmac.new(_secret().encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return None
    return _load_session(session_id)


def persona_of(user_id: str) -> str | None:
    if not user_id or not _presentation_on():
        return None
    row = _load_user(user_id)
    if not row:
        return None
    persona = str(row.get("persona") or "")
    if persona in _PERSONAS:
        return persona
    return None


def _real_village_operator(user_id: str) -> dict | None:
    from services.supabase_client import get_operator_by_kakao_id

    row = get_operator_by_kakao_id(user_id)
    if row and (row.get("role") or "village") == "village":
        return row
    return None


def _program_switch_allowed(user_id: str) -> bool:
    row = _real_village_operator(user_id)
    if row is None:
        from services.supabase_client import get_operator_by_kakao_id

        return get_operator_by_kakao_id(user_id) is None
    return str(row.get("village_id") or "") == DEMO_VILLAGE_ID


def set_demo_persona(user_id: str, persona: str) -> bool:
    """테스트와 화면이 역할을 저장한다. 허용되지 않으면 바꾸지 않는다."""
    if persona not in _PERSONAS or not user_id:
        return False
    if persona == "program" and not _program_switch_allowed(user_id):
        return False
    session = _ensure_session(user_id)
    session["persona"] = persona
    session["updated_at"] = _now()
    _remember(session)
    _persist_session(session)
    return True


def choose_persona(token: str, persona: str) -> dict:
    session = session_from_token(token)
    if session is None:
        return {"ok": False, "message": "역할을 다시 열어 주세요."}
    if persona not in _PERSONAS:
        return {"ok": False, "message": "체험객, 사무장, 체험 담당 중에서 고릅니다."}
    user_id = str(session.get("kakao_user_id") or "")
    if not set_demo_persona(user_id, persona):
        return {"ok": False, "message": "담당 보기는 예시 갯벌마을 계정에서만 바뀝니다."}
    message = persona_message(user_id, persona)
    from services.kakao_client import notify_demo_role_chosen

    pushed = notify_demo_role_chosen(user_id, message)
    return {"ok": True, "message": message, "persona": persona, "pushed": pushed}


def persona_message(user_id: str, persona: str) -> str:
    limited = _real_village_operator(user_id) is None
    if persona == "guest":
        return "체험객으로 바꿨습니다. 예약하기와 내 예약을 씁니다."
    if persona == "village" and limited:
        return "사무장으로 바꿨습니다. 직접 만든 예약만 바꿀 수 있습니다."
    if persona == "village":
        return "사무장으로 바꿨습니다. 예약 현황, 달력, 홍보 사진을 씁니다."
    if limited:
        return "체험 담당으로 바꿨습니다. 직접 만든 예약만 봅니다."
    return "체험 담당으로 바꿨습니다. 달력은 보기만 합니다."


def current_persona_label(session: dict | None) -> str:
    labels = {"guest": "체험객", "village": "사무장", "program": "체험 담당"}
    if not session:
        return "아직 고르지 않음"
    return labels.get(str(session.get("persona") or ""), "아직 고르지 않음")


def ensure_demo_staff() -> dict | None:
    """예시 갯벌마을 시연 담당 한 명. 이미 있으면 그 행을 쓴다."""
    from services.supabase_client import get_operator_by_kakao_id, insert_operator
    from services.village_programs import program_key

    existing = get_operator_by_kakao_id(DEMO_STAFF_KAKAO_ID)
    if existing:
        return existing
    try:
        return insert_operator(
            {
                "village_id": DEMO_VILLAGE_ID,
                "kakao_user_id": DEMO_STAFF_KAKAO_ID,
                "operator_name": DEMO_STAFF_NAME,
                "role": "program",
                "program_key": program_key("소금체험"),
                "is_active": True,
                "registered_at": _now(),
            }
        )
    except Exception:
        return get_operator_by_kakao_id(DEMO_STAFF_KAKAO_ID)


def overlay_role(user_id: str, row: dict | None) -> dict | None:
    """고른 역할이 저장된 등록과 다를 때만 역할 딕셔너리를 돌려준다."""
    persona = persona_of(user_id)
    if persona is None:
        return None
    if persona == "guest":
        return {"mode": "tourist", "village_id": None, "role": None, "program_key": None}
    if persona == "village":
        if row and (row.get("role") or "village") == "village":
            return None
        return {
            "mode": "operator",
            "village_id": DEMO_VILLAGE_ID,
            "role": "village",
            "program_key": None,
            "limited": True,
        }
    if persona != "program":
        return None
    if row and (row.get("role") or "village") == "village" and str(row.get("village_id") or "") == DEMO_VILLAGE_ID:
        staff = ensure_demo_staff()
        if not staff:
            return None
        return {
            "mode": "operator",
            "village_id": DEMO_VILLAGE_ID,
            "role": "program",
            "program_key": staff.get("program_key"),
        }
    if row:
        return None
    staff = ensure_demo_staff()
    if not staff:
        return None
    return {
        "mode": "operator",
        "village_id": DEMO_VILLAGE_ID,
        "role": "program",
        "program_key": staff.get("program_key"),
        "limited": True,
    }


def operator_for_skill(user_id: str) -> dict | None:
    """달력과 글에 쓸 운영자. 예시 갯벌마을 담당 보기는 시연 담당 행을 쓴다."""
    from services.auth import resolve_kakao_role
    from services.supabase_client import get_operator_by_kakao_id

    role = resolve_kakao_role(user_id)
    if role["mode"] != "operator" or role.get("limited"):
        return None
    if role.get("role") == "program" and role.get("village_id") == DEMO_VILLAGE_ID:
        staff = ensure_demo_staff()
        if staff:
            return staff
    return get_operator_by_kakao_id(user_id)


def is_limited(user_id: str) -> bool:
    from services.auth import resolve_kakao_role

    return bool(resolve_kakao_role(user_id).get("limited"))


def mark_guest_demo(customer_id: str, booking_id) -> None:
    """심사 계정이 체험객으로 만든 예약. 마을 사무장 목록에서는 뺀다."""
    if not _presentation_on() or booking_id in (None, ""):
        return
    if persona_of(customer_id) != "guest":
        return
    if _real_village_operator(customer_id):
        return
    try:
        number = int(booking_id)
    except (TypeError, ValueError):
        return
    _marks.add(number)
    if _table_ready["marks"] is False:
        return
    from services.supabase_client import get_supabase_client

    client = get_supabase_client()
    if not client:
        return
    try:
        client.table("demo_booking_marks").upsert(
            {"booking_id": number, "kakao_user_id": customer_id},
            on_conflict="booking_id",
        ).execute()
    except Exception:
        _table_ready["marks"] = False
        return
    _table_ready["marks"] = True


def marked_booking_ids() -> set[int]:
    found = set(_marks)
    if _table_ready["marks"] is False:
        return found
    from services.supabase_client import get_supabase_client

    client = get_supabase_client()
    if not client:
        return found
    try:
        result = client.table("demo_booking_marks").select("booking_id").execute()
    except Exception:
        _table_ready["marks"] = False
        return found
    _table_ready["marks"] = True
    for row in result.data or []:
        try:
            found.add(int(row.get("booking_id")))
        except (TypeError, ValueError):
            continue
    return found


def without_marked_bookings(rows: list[dict]) -> list[dict]:
    hidden = marked_booking_ids()
    if not hidden:
        return rows
    return [row for row in rows if row.get("booking_id") not in hidden]


def rows_for_demo_viewer(rows: list[dict], user_id: str) -> list[dict]:
    if is_limited(user_id):
        return [row for row in rows if str(row.get("customer_kakao_id") or "") == user_id]
    return without_marked_bookings(rows)
