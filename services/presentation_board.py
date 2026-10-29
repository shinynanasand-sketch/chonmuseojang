"""발표 보드용 문장과 결과. 고객 이름과 카카오 사용자 ID는 넣지 않는다."""

import hmac
import os

from config import KAKAO_CHANNEL_URL
from services.booking import booking_summary, list_bookings_for_village
from services.calendar_link import calendar_page_url
from services.guest_book import operating_names
from services.kakao_home import list_kakao_booking_villages
from services.supabase_client import get_village_by_id, get_village_operator, list_contents
from services.village_programs import program_labels
from services.village_promo import public_village_promo

_INTRO = "소개글"
_SNS = "SNS홍보문구"
_FALLBACK_PROGRAM = "체험이름"
_EXAMPLE_BOOKING = 7
_SENTENCE_REPLY = "예약번호와 대기로 접수됩니다."
_PHOTO_PROMPT = "사진을 한 장 올려 주세요."
_APPROVE_REPLY = "예약이 승인되었습니다."
_REJECT_REPLY = "예약이 거절되었습니다."


def _program_label(village: dict) -> str:
    names = operating_names(village)
    if names:
        return names[0]
    labels = program_labels(village)
    if labels:
        return labels[0]
    return _FALLBACK_PROGRAM


def _http_photo(row: dict) -> str:
    url = str(row.get("photo_url") or "").strip()
    if url.startswith("https://") or url.startswith("http://"):
        return url
    return ""


def _latest_promo(village_id: str) -> dict | None:
    latest: dict[str, dict] = {}
    for row in list_contents(village_id=village_id):
        kind = row.get("content_type")
        if kind in {_INTRO, _SNS}:
            latest[kind] = row
    if not latest:
        return None
    intro = latest.get(_INTRO, {})
    sns = latest.get(_SNS, {})
    published = public_village_promo(village_id) or {}
    page = ""
    if (published.get("intro") or "").strip() or (published.get("sns") or "").strip():
        page = f"/village/{village_id}"
    draft = any(row and not row.get("is_public") for row in (intro, sns) if row.get("body"))
    return {
        "intro": str(intro.get("body") or ""),
        "sns": str(sns.get("body") or ""),
        "photo_url": _http_photo(intro) or _http_photo(sns),
        "draft": draft,
        "village_page": page,
    }


def _place(row: dict) -> str:
    """예약 카드가 마을 이름 뒤에 시군을 붙이는 것과 같다."""
    return " ".join(
        part
        for part in (str(row.get("village_name") or "").strip(), str(row.get("sigungu") or "").strip())
        if part
    )


def _pending_id(rows: list[dict]) -> int | None:
    pending = [row for row in rows if row.get("status") == "pending" and row.get("booking_id") is not None]
    if not pending:
        return None
    return int(max(pending, key=lambda row: int(row["booking_id"]))["booking_id"])


def presentation_board() -> dict:
    """예약 가능 마을 하나의 복사 문장, 예약 줄, 최근 홍보."""
    villages = list_kakao_booking_villages()
    board = {
        "connected": False,
        "village_name": "",
        "extra_note": "",
        "book_utterance": "예약하기",
        "sentence_utterance": f"{_FALLBACK_PROGRAM} 2026-11-01 10:00 30명",
        "calendar_utterance": f"{_FALLBACK_PROGRAM} 2026-11-01 광주소등학교 30명",
        "approve_utterance": f"{_EXAMPLE_BOOKING}번 승인",
        "reject_utterance": f"{_EXAMPLE_BOOKING}번 거절",
        "approve_is_example": True,
        "book_reply": "",
        "sentence_reply": _SENTENCE_REPLY,
        "photo_prompt": _PHOTO_PROMPT,
        "approve_reply": _APPROVE_REPLY,
        "reject_reply": _REJECT_REPLY,
        "booking_lines": [],
        "promo": None,
        "channel_url": KAKAO_CHANNEL_URL,
    }
    if not villages:
        return board
    chosen = villages[0]
    village = get_village_by_id(chosen["village_id"]) or chosen
    label = _program_label(village)
    name = str(chosen.get("village_name") or "").strip()
    place = _place(village)
    rows = list_bookings_for_village(str(chosen["village_id"]))
    pending = _pending_id(rows)
    board.update(
        {
            "connected": True,
            "village_name": name,
            "extra_note": "다른 예약 마을도 고를 수 있습니다." if len(villages) > 1 else "",
            "book_utterance": f"예약하기 {name}".strip(),
            "sentence_utterance": f"{label} 2026-11-01 10:00 30명",
            "calendar_utterance": f"{label} 2026-11-01 광주소등학교 30명",
            "book_reply": f"{place}. 달력에서 체험, 날짜, 시간을 고릅니다." if place else "",
            "booking_lines": [booking_summary(row) for row in rows[:5]],
            "promo": _latest_promo(str(chosen["village_id"])),
        }
    )
    if pending is not None:
        board["approve_utterance"] = f"{pending}번 승인"
        board["reject_utterance"] = f"{pending}번 거절"
        board["approve_is_example"] = False
    return board


def presentation_calendar_url(password: str) -> str | None:
    """시연 비밀번호가 맞을 때만 첫 예약 마을의 달력 주소를 준다."""
    expected = os.getenv("PRESENTATION_CALENDAR_PASSWORD", "")
    given = (password or "").strip()
    if not expected or not given or len(expected) != len(given):
        return None
    if not hmac.compare_digest(expected, given):
        return None
    villages = list_kakao_booking_villages()
    if not villages:
        return None
    operator = get_village_operator(str(villages[0]["village_id"]))
    if not operator:
        return None
    return calendar_page_url(operator)
