"""Phase A 블록. 응답에 context를 넣지 않는다."""

import re

from urllib.parse import urlparse

from models.kakao_schemas import KakaoSkillRequest
from services import booking, review
from services.auth import get_operator_by_kakao_id, register_operator, register_operator_with_ids, resolve_kakao_role
from services.calendar_link import attach_calendar_card
from services.kakao_client import (
    allow_external,
    attach_guide_card,
    build_error_skill_response,
    build_skill_response,
    guide_skill_response,
    notify_booking_decided,
    seconds_remaining,
    time_budget_response,
)
from services.kakao_params import booking_id_from_params, kakao_photo_url, parse_sys_date, representative
from services.operator_assistant import (
    PhotoRejected,
    _kakao_photo_host,
    download_kakao_photo,
    save_operator_photo_draft,
)
from services.program_share import list_calendar, list_program_notes, save_calendar_entry, save_program_note
from services.recommend import recommendation_lines, recommend_for_kakao
from services.supabase_client import get_village_by_id, list_recommend_villages
from services.village_programs import program_labels

_BLOCKS = {
    "마을 추천": "recommend",
    "마을추천": "recommend",
    "후기 조회": "reviews",
    "예약 현황 조회": "status",
    "예약승인": "approve",
    "예약거절": "reject",
    "운영자 등록": "register",
    "운영자등록": "register",
    "홍보 사진": "promo_photo",
    "체험 글 저장": "note_save",
    "체험 글 조회": "note_list",
    "체험 달력 등록": "calendar_save",
    "체험 달력 조회": "calendar_list",
    "예약하기": "book_menu",
    "내 예약": "my_bookings",
    "후기 보기": "review_menu",
}

_APPROVE_GUIDE = "몇 번 예약을 승인하시겠어요? 예시: 7번 승인"
_REJECT_GUIDE = "몇 번 예약을 거절하시겠어요? 예시: 7번 거절"
_OPERATOR_ONLY = "등록된 운영자만 승인/거절할 수 있습니다."
_STATUS_HINT = "운영자는 등록 [마을명] [코드]로 등록할 수 있습니다."
_OTHER_VILLAGE = "이 예약을 처리할 권한이 없습니다."
_REGISTER_NEED = "마을명과 등록 코드를 한 문장으로 말해 주세요. 예시: 예시 갯벌마을 GB-001"
_PHOTO_GUIDE = "사진을 한 장 올려 주세요."
_PHOTO_FAILED = "홍보문구를 만들지 못했습니다."
_PHOTO_PUBLISH = "웹에서 관광객에게 공개를 누르면 마을 화면에 나갑니다."
_VILLAGE_ONLY = "예약·홍보는 마을 운영자만 할 수 있습니다."
_NOTE_ONLY = "체험 글은 체험 담당만 저장할 수 있습니다."
_CALENDAR_ONLY = "체험 달력은 마을 운영자만 등록할 수 있습니다."
_SHARE_ONLY = "등록된 운영자만 체험 글과 달력을 볼 수 있습니다."
_NOTE_NEED = "체험 글 뒤에 내용을 말해 주세요."
_CALENDAR_NEED = (
    "체험 이름, 날짜, 단체, 인원을 한 문장에 넣어 주세요. 예: 조개잡이 2026-11-01 광주소등학교 30명"
)
_STATUS_LABEL = {"pending": "대기", "confirmed": "승인", "rejected": "거절"}
_ASK_PROMPT = "체험 종류나 시군 이름을 넣어 질문해 주세요."
_REVIEW_LEAD = "후기를 보려면 후기 보기 뒤에 마을 이름을 말해 주세요."
_REVIEW_EMPTY = "아직 후기를 볼 마을이 없습니다. 후기 보기 뒤에 마을 이름을 말해 주세요."
_REVIEW_BUTTONS = 6
_REVIEW_TEXT_LIMIT = 1000
_BOOK_EXAMPLE = "체험 이름 2026-11-01 30명"
_MENU_RECOMMEND = {"마을 추천", "마을추천"}
_REGISTER_REASONS = {
    "bad_format": _REGISTER_NEED,
    "village_not_found": "등록 코드가 마을과 맞지 않습니다.",
    "code_mismatch": "등록 코드가 마을과 맞지 않습니다.",
    "already_registered": "이 마을에는 이미 마을 운영자가 있습니다. 체험 이름을 붙여 주세요.",
    "village_operator_required": "먼저 마을 운영자를 등록해 주세요.",
    "program_not_found": "이 마을 체험이 아닙니다.",
    "program_taken": "이 체험에는 이미 담당자가 있습니다.",
}


def _skill_lines(title: str, lines: list[str], total: int) -> dict:
    shown = [line for line in lines if line][:5]
    heading = "최근 5건" if total > 5 else title
    return build_skill_response(heading, " / ".join(shown))


def _https_host(url: str, allowed) -> bool:
    parsed = urlparse(url or "")
    return parsed.scheme == "https" and allowed(parsed.hostname or "")


def _kakao_photo_address(url: str) -> bool:
    """이미지 플러그인은 http, 그 외 카카오 사진은 https다."""
    parsed = urlparse(url or "")
    return parsed.scheme in {"http", "https"} and _kakao_photo_host(parsed.hostname or "")


def _kakao_callback_host(host: str) -> bool:
    name = (host or "").lower().rstrip(".")
    return name == "kakao.com" or name.endswith(".kakao.com")


def promo_photo_should_defer(payload: KakaoSkillRequest) -> bool:
    """운영자의 카카오 사진과 콜백 주소가 있을 때만 별도 실행으로 넘긴다."""
    if (payload.intent.name or "").strip() != "홍보 사진":
        return False
    user_id = str(payload.userRequest.user.get("id") or "")
    if resolve_kakao_role(user_id)["mode"] != "operator":
        return False
    if not _kakao_photo_address(kakao_photo_url(payload)):
        return False
    return _https_host(payload.userRequest.callbackUrl, _kakao_callback_host)


def finish_promo_photo(payload: KakaoSkillRequest) -> dict:
    user_id = str(payload.userRequest.user.get("id") or "")
    from services.kakao_client import bind_reply_user, reset_reply_user

    token = bind_reply_user(user_id)
    try:
        return _promo_photo(user_id, resolve_kakao_role(user_id), payload)
    finally:
        reset_reply_user(token)


def handle_phase_a(payload: KakaoSkillRequest) -> dict | None:
    """아는 블록만 처리한다. 추천과 등록은 운영자 조회 없이 간다."""
    user_id = str(payload.userRequest.user.get("id") or "")
    utterance = (payload.userRequest.utterance or "").strip()
    name = (payload.intent.name or "").strip()
    if utterance in {"등록 안내", "사용 안내"} or name in {"등록 안내", "사용 안내"}:
        return guide_skill_response(utterance if utterance in {"등록 안내", "사용 안내"} else name)
    menu = _tourist_menu(user_id, utterance)
    if menu is not None:
        return menu
    kind = _BLOCKS.get(name)
    if kind is None:
        return None
    if kind == "recommend":
        return _recommend(payload.userRequest.utterance)
    if kind == "book_menu":
        return _booking_guide(user_id, utterance) if not utterance else None
    if kind == "my_bookings":
        return _my_bookings(user_id)
    if kind == "review_menu":
        return _review_by_speech(utterance)
    if kind == "reviews":
        if not allow_external():
            return time_budget_response()
        return _reviews(payload)
    if kind == "register":
        return _register(user_id, payload)
    if kind in {"note_save", "note_list", "calendar_save", "calendar_list"}:
        if not allow_external():
            return time_budget_response()
        return _share(kind, user_id, payload)
    if not allow_external():
        return time_budget_response()
    role = resolve_kakao_role(user_id)
    if kind == "promo_photo":
        if role.get("role") == "program":
            return build_error_skill_response(_VILLAGE_ONLY)
        return _promo_photo(user_id, role, payload)
    if role["mode"] != "operator":
        hint = _STATUS_HINT if kind == "status" else _OPERATOR_ONLY
        body = build_error_skill_response(hint)
        if kind == "status":
            return attach_guide_card(body)
        return body
    if role.get("role") == "program":
        return build_error_skill_response(_VILLAGE_ONLY)
    if kind == "status":
        return _status(str(role["village_id"]))
    return _decide(kind, str(role["village_id"]), payload)


def _tourist_menu(user_id: str, utterance: str) -> dict | None:
    """버튼 발화는 블록 이름과 상관없이 같은 안내를 낸다."""
    text = (utterance or "").strip()
    if text in _MENU_RECOMMEND:
        return build_error_skill_response(_ASK_PROMPT)
    if text == "예약하기" or text.startswith("예약하기 "):
        return _booking_guide(user_id, text)
    if text == "내 예약":
        return _my_bookings(user_id)
    if text == "후기 보기" or text.startswith("후기 보기 "):
        return _review_by_speech(text)
    return None


def _place_name(row: dict) -> str:
    return " ".join(part for part in (row.get("village_name"), row.get("sigungu")) if part)


def _booking_village(spoken: str, rows: list[dict]) -> dict | None:
    exact = [row for row in rows if str(row.get("village_name") or "").strip() == spoken]
    if len(exact) == 1:
        return exact[0]
    for row in rows:
        if _place_name(row) == spoken:
            return row
    return None


def _booking_choices(rows: list[dict]) -> dict:
    names = [_place_name(row) for row in rows]
    text = f"{' / '.join(names)}. 예약할 마을 이름을 말해 주세요."
    body = build_skill_response("예약하기", text)
    buttons = []
    for row in rows[:6]:
        name = str(row.get("village_name") or "").strip()
        if not name:
            continue
        buttons.append({"label": name[:14], "action": "message", "messageText": f"예약하기 {name}"})
    return _prepend_replies(body, buttons)


def _booking_card(user_id: str, row: dict) -> dict:
    from config import KAKAO_CARD_IMAGE_URL
    from services.guest_book import issue_guest_book_link

    place = _place_name(row)
    body = build_skill_response("예약하기", f"{place}. 달력에서 체험, 날짜, 시간을 고릅니다.")
    outputs = body.setdefault("template", {}).setdefault("outputs", [])
    outputs.append(
        {
            "basicCard": {
                "title": "체험 달력",
                "description": "날짜와 시간을 눌러 예약합니다.",
                "thumbnail": {"imageUrl": KAKAO_CARD_IMAGE_URL},
                "buttons": [
                    {
                        "action": "webLink",
                        "label": "달력으로 예약",
                        "webLinkUrl": issue_guest_book_link(user_id, str(row.get("village_id") or "")),
                    }
                ],
            }
        }
    )
    return body


def _booking_guide(user_id: str, utterance: str = "") -> dict:
    """예약은 만들지 않고, 그 마을 달력 링크만 안내한다."""
    if not allow_external():
        return time_budget_response()
    if not user_id:
        return build_error_skill_response("다시 시도해 주세요.")
    from services.kakao_home import list_kakao_booking_villages

    rows = list_kakao_booking_villages()
    if not rows:
        return build_skill_response(
            "예약하기",
            f"아직 예약할 수 있는 마을이 없습니다. {_BOOK_EXAMPLE}처럼 말해 주세요.",
        )
    spoken = (utterance or "").strip()
    if spoken.startswith("예약하기"):
        spoken = spoken[len("예약하기") :].strip()
    if not spoken:
        if len(rows) == 1:
            return _booking_card(user_id, rows[0])
        return _booking_choices(rows)
    chosen = _booking_village(spoken, rows)
    if chosen is None:
        return _booking_choices(rows)
    return _booking_card(user_id, chosen)


def _my_bookings(user_id: str) -> dict:
    if not allow_external():
        return time_budget_response()
    lines = booking.format_booking_lines(booking.list_my_bookings(user_id))
    return build_skill_response("내 예약", lines)


def _prepend_replies(body: dict, extras: list[dict]) -> dict:
    if not extras:
        return body
    template = body.setdefault("template", {})
    current = list(template.get("quickReplies") or [])
    template["quickReplies"] = (extras + current)[:10]
    return body


def _review_cursor(spoken: str) -> tuple[str, int]:
    matched = re.fullmatch(r"(?P<name>.*?) #(?P<start>\d+)$", spoken)
    if not matched:
        return spoken, 1
    start = int(matched.group("start"))
    return matched.group("name").strip(), start if start > 0 else 1


def _review_ask() -> dict:
    """예약할 수 있는 마을과, 그 이름을 붙인 발화 버튼을 안내한다."""
    if not allow_external():
        return time_budget_response()
    from services.kakao_home import list_kakao_booking_villages

    rows = list_kakao_booking_villages()
    if not rows:
        return build_error_skill_response(_REVIEW_EMPTY)
    names = [
        " ".join(part for part in (row.get("village_name"), row.get("sigungu")) if part)
        for row in rows
    ]
    example = str(rows[0].get("village_name") or "").strip()
    text = f"{_REVIEW_LEAD} {' / '.join(names)}. 예: 후기 보기 {example}"
    body = build_error_skill_response(text)
    buttons = []
    for row in rows[:_REVIEW_BUTTONS]:
        name = str(row.get("village_name") or "").strip()
        if not name:
            continue
        buttons.append(
            {
                "label": name[:14],
                "action": "message",
                "messageText": f"후기 보기 {name}",
            }
        )
    return _prepend_replies(body, buttons)


def _review_by_speech(utterance: str) -> dict:
    spoken = (utterance or "").strip()
    if spoken.startswith("후기 보기"):
        spoken = spoken[len("후기 보기") :].strip()
    spoken, start = _review_cursor(spoken)
    if not spoken:
        return _review_ask()
    if not allow_external():
        return time_budget_response()
    from services.supabase_client import list_villages_by_name

    rows = list_villages_by_name(spoken)
    if not rows and " " in spoken:
        sigungu, name = spoken.split(" ", 1)
        rows = list_villages_by_name(name.strip(), sigungu=sigungu.strip())
    sigungus = {str(row.get("sigungu") or "").strip() for row in rows}
    if not rows or len(sigungus) > 1:
        return _review_ask()
    village_name = str(rows[0].get("village_name") or "").strip()
    return _review_lines(str(rows[0].get("village_id") or ""), village_name, start)


def _recommend(utterance: str) -> dict:
    query = (utterance or "").strip()
    if not query or query in _MENU_RECOMMEND:
        return build_error_skill_response(_ASK_PROMPT)
    if not allow_external():
        return time_budget_response()
    villages = list_recommend_villages()
    matches = recommend_for_kakao(query, villages, seconds_remaining())
    if not matches:
        return build_error_skill_response(
            "조건에 맞는 마을을 찾지 못했습니다. 조건을 조금 넓혀 주세요."
        )
    items = recommendation_lines(matches, villages)
    return _skill_lines("마을 추천", items, len(items))


def _reviews(payload: KakaoSkillRequest) -> dict:
    village_id = str(representative(payload.action.params, "village_id") or "").strip()
    if not village_id:
        return _review_ask()
    village = get_village_by_id(village_id) or {}
    village_name = str(village.get("village_name") or village_id).strip()
    return _review_lines(village_id, village_name, 1)


def _review_page_text(title: str, description: str) -> str:
    text = f"{title}. {description}".strip() if description else title
    return " ".join(text.split())


def _review_lines(village_id: str, village_name: str, start: int) -> dict:
    rows = review.list_reviews_for_village(village_id)
    if not rows:
        return build_error_skill_response("등록된 후기가 없습니다.")
    lines = [
        " ".join(part for part in (f"별점 {row.get('rating')}", str(row.get("comment") or "").strip()) if part)
        for row in rows
    ]
    total = len(lines)
    index = min(max(start, 1), total) - 1
    chosen: list[str] = []
    for line in lines[index:]:
        trial = chosen + [line]
        title = f"{total}건 중 {index + 1}-{index + len(trial)}건"
        if len(_review_page_text(title, " / ".join(trial))) > _REVIEW_TEXT_LIMIT:
            break
        chosen = trial
    if not chosen:
        chosen = [lines[index]]
    title = f"{total}건 중 {index + 1}-{index + len(chosen)}건"
    body = build_skill_response(title, " / ".join(chosen))
    next_index = index + len(chosen)
    if next_index >= total:
        return body
    return _prepend_replies(
        body,
        [
            {
                "label": "다음 후기",
                "action": "message",
                "messageText": f"후기 보기 {village_name} #{next_index + 1}",
            }
        ],
    )


def _status(village_id: str) -> dict:
    if not allow_external():
        return time_budget_response()
    rows = booking.list_bookings_for_village(village_id)
    if not rows:
        return build_error_skill_response("예약이 없습니다.")
    lines = []
    for row in rows:
        lines.append(booking.booking_summary(row))
    return _skill_lines("예약 현황", lines, len(rows))


def _promo_photo(user_id: str, role: dict, payload: KakaoSkillRequest) -> dict:
    if role["mode"] != "operator":
        return build_error_skill_response(_STATUS_HINT)
    url = kakao_photo_url(payload)
    if not url:
        return build_error_skill_response(_PHOTO_GUIDE)
    if not _kakao_photo_address(url):
        return build_error_skill_response(_PHOTO_GUIDE)
    if not _https_host(payload.userRequest.callbackUrl, _kakao_callback_host):
        return build_error_skill_response(_PHOTO_FAILED)
    try:
        photo = download_kakao_photo(url)
    except PhotoRejected as exc:
        return build_error_skill_response(exc.message)
    operator = get_operator_by_kakao_id(user_id)
    if not operator:
        return build_error_skill_response(_STATUS_HINT)
    result = save_operator_photo_draft(operator, photo)
    if not result.get("saved"):
        return build_error_skill_response(str(result.get("message") or _PHOTO_FAILED))
    bodies = {row.get("content_type"): row.get("body") for row in result.get("contents") or []}
    description = f"{bodies.get('소개글', '')} {bodies.get('SNS홍보문구', '')} {_PHOTO_PUBLISH}"
    return build_skill_response("홍보문구", description)


def _register(user_id: str, payload: KakaoSkillRequest) -> dict:
    params = payload.action.params
    village_id = str(representative(params, "village_id") or "").strip()
    code = str(representative(params, "registration_code") or "").strip()
    program = str(representative(params, "program_label") or "").strip()
    utterance = payload.userRequest.utterance or ""
    if not program:
        program = _program_after_code(utterance, code)
    if village_id and code:
        if not allow_external():
            return time_budget_response()
        result = register_operator_with_ids(user_id, village_id, code, program)
    elif utterance.strip():
        if not allow_external():
            return time_budget_response()
        result = register_operator(user_id, utterance)
    else:
        return attach_guide_card(build_error_skill_response(_REGISTER_NEED))
    if result.get("ok"):
        if result.get("role") == "program":
            text = f"{result['village_id']} 체험 담당으로 등록되었습니다."
        else:
            text = f"{result['village_id']} 운영자로 등록되었습니다."
        return build_skill_response("등록 완료", text)
    reason = str(result.get("reason") or "")
    message = _REGISTER_REASONS.get(reason, "등록 코드가 마을과 맞지 않습니다.")
    return attach_guide_card(build_error_skill_response(message))


def _decide(kind: str, village_id: str, payload: KakaoSkillRequest) -> dict:
    booking_id = booking_id_from_params(payload.action.params)
    if booking_id is None:
        guide = _APPROVE_GUIDE if kind == "approve" else _REJECT_GUIDE
        return build_error_skill_response(guide)
    existing = booking.get_booking_by_id(booking_id)
    if not existing:
        return build_error_skill_response("예약을 찾을 수 없습니다.")
    if existing.get("village_id") != village_id:
        return build_error_skill_response(_OTHER_VILLAGE)
    if kind == "approve":
        booking.update_booking_status(booking_id, "confirmed")
        notify_booking_decided(existing, "approve")
        return build_skill_response("승인 완료", "예약이 승인되었습니다.")
    booking.update_booking_status(booking_id, "rejected")
    notify_booking_decided(existing, "reject")
    return build_skill_response("거절 완료", "예약이 거절되었습니다.")


def _program_after_code(utterance: str, code: str) -> str:
    text = (utterance or "").strip()
    if text.startswith("등록 "):
        text = text[3:].strip()
    if not code or code not in text:
        return ""
    return text.split(code, 1)[1].strip()


def _note_body(utterance: str) -> str:
    text = (utterance or "").strip()
    for prefix in ("체험 글 저장", "체험 글"):
        if text.startswith(prefix):
            return text[len(prefix) :].strip()
    return text


def _label_in_text(village_id: str, text: str) -> str:
    village = get_village_by_id(village_id) or {}
    found = [label for label in program_labels(village) if label and label in text]
    if not found:
        return ""
    return max(found, key=len)


def _share(kind: str, user_id: str, payload: KakaoSkillRequest) -> dict:
    operator = get_operator_by_kakao_id(user_id)
    if not operator:
        return build_error_skill_response(_SHARE_ONLY)
    if kind == "note_list":
        rows = list_program_notes(operator).get("notes") or []
        if not rows:
            return build_error_skill_response("등록된 체험 글이 없습니다.")
        lines = [f"{row.get('label')} {row.get('body')}".strip() for row in rows]
        return _skill_lines("체험 글", lines, len(rows))
    if kind == "calendar_list":
        rows = list_calendar(operator).get("entries") or []
        if not rows:
            body = build_error_skill_response("등록된 체험 일정이 없습니다.")
        else:
            lines = [
                (
                    f"{row.get('label')} {row.get('visit_date')} {row.get('group_name')} "
                    f"{row.get('num_people')}명"
                )
                for row in rows
            ]
            body = _skill_lines("체험 달력", lines, len(rows))
        return attach_calendar_card(body, operator)
    if kind == "note_save":
        body = _note_body(payload.userRequest.utterance or "")
        if not body:
            return build_error_skill_response(_NOTE_NEED)
        result = save_program_note(operator, body)
        if result.get("ok"):
            return build_skill_response("체험 글", f"{result['label']} 내용을 저장했습니다.")
        if result.get("reason") == "read_only":
            return build_error_skill_response(_NOTE_ONLY)
        if result.get("reason") == "program_not_found":
            return build_error_skill_response("이 마을 체험이 아닙니다.")
        return build_error_skill_response(_NOTE_NEED)
    label, visit_date, group_name, num_people = _calendar_fields(operator, payload)
    if not label or not visit_date or not group_name or num_people is None:
        return build_error_skill_response(_CALENDAR_NEED)
    result = save_calendar_entry(operator, label, visit_date, group_name, num_people)
    if result.get("ok"):
        line = f"{result['label']} {result['visit_date']} {result['group_name']} {result['num_people']}명"
        return build_skill_response("체험 달력", f"{line} 일정을 등록했습니다.")
    if result.get("reason") == "forbidden":
        return build_error_skill_response(_CALENDAR_ONLY)
    if result.get("reason") == "program_not_found":
        return build_error_skill_response("이 마을 체험이 아닙니다.")
    return build_error_skill_response(_CALENDAR_NEED)


def _group_and_count(text: str) -> tuple[str, int | None]:
    found = re.search(r"(\d+)\s*명", text or "")
    if not found:
        return "", None
    count = int(found.group(1))
    group = " ".join(text[: found.start()].split())
    if count < 1 or not group:
        return "", None
    return group, count


def _calendar_fields(operator: dict, payload: KakaoSkillRequest) -> tuple[str, str, str, int | None]:
    params = payload.action.params
    utterance = payload.userRequest.utterance or ""
    visit_date = parse_sys_date(representative(params, "visit_date")) or ""
    if not visit_date:
        found = re.search(r"\d{4}-\d{2}-\d{2}", utterance)
        visit_date = found.group(0) if found else ""
    label = str(representative(params, "program_label") or "").strip()
    if not label:
        label = _label_in_text(str(operator.get("village_id") or ""), utterance)
    remainder = utterance
    for piece in ("체험 달력 등록", "체험 달력", label, visit_date):
        remainder = remainder.replace(piece, " ")
    group_name, num_people = _group_and_count(" ".join(remainder.split()))
    if num_people is None:
        group_name, num_people = _group_and_count(str(representative(params, "note") or ""))
    return label, visit_date, group_name, num_people
