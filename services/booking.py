"""예약 생성/조회/상태변경."""

import re
from datetime import date, datetime, timedelta, timezone

from services.supabase_client import (
    insert_booking,
    list_bookings,
    reset_booking_store,
    save_booking_status,
    update_booking,
)

_DATE_IN_TEXT = re.compile(r"\d{4}-\d{2}-\d{2}")
_COUNT_IN_TEXT = re.compile(r"(\d+)\s*명")


_shown_week: dict[str, date] = {}


def reset_bookings() -> None:
    reset_booking_store()
    _shown_week.clear()


def _slot_key(row: dict) -> tuple[str, str, str, str, str]:
    return (
        str(row.get("customer_kakao_id") or ""),
        str(row.get("village_id") or ""),
        str(row.get("program_key") or ""),
        str(row.get("visit_date") or "")[:10],
        str(row.get("visit_time") or "").strip()[:5],
    )


def _open_booking(row: dict) -> dict | None:
    """같은 손님·체험·일시의 대기 또는 승인 예약. 거절된 예약은 다시 받을 수 있다."""
    matches = [
        existing
        for existing in list_bookings(
            village_id=str(row.get("village_id") or ""),
            customer_kakao_id=str(row.get("customer_kakao_id") or ""),
        )
        if existing.get("status") in ("pending", "confirmed") and _slot_key(existing) == _slot_key(row)
    ]
    pending = [existing for existing in matches if existing.get("status") == "pending"]
    chosen = pending or matches
    return chosen[-1] if chosen else None


def _clean_group(value) -> str:
    return " ".join(str(value or "").split())


def create_booking(
    village_id: str,
    customer_kakao_id: str,
    visit_date: str,
    num_people: int,
    customer_name: str | None = None,
    program_label: str | None = None,
    visit_time: str | None = None,
    group_name: str | None = None,
) -> dict:
    group = _clean_group(group_name)
    row = {
        "village_id": village_id,
        "customer_kakao_id": customer_kakao_id,
        "customer_name": customer_name,
        "visit_date": str(visit_date)[:10],
        "num_people": num_people,
        "status": "pending",
    }
    if group:
        row["group_name"] = group
    clock = (visit_time or "").strip()[:5]
    if clock:
        row["visit_time"] = clock
    label = (program_label or "").strip()
    if label:
        from services.village_programs import program_key

        row["program_label"] = label
        row["program_key"] = program_key(label)
    existing = _open_booking(row)
    if existing:
        found = dict(existing)
        found["already_open"] = True
        found["headcount_updated"] = False
        found["group_updated"] = False
        if existing.get("status") == "pending":
            changes = {}
            if int(existing.get("num_people") or 0) != int(num_people):
                changes["num_people"] = num_people
            if group and group != _clean_group(existing.get("group_name")):
                changes["group_name"] = group
            if changes:
                updated = update_booking(int(existing["booking_id"]), changes) or found
                updated = dict(updated)
                updated["already_open"] = True
                updated["headcount_updated"] = "num_people" in changes
                updated["group_updated"] = "group_name" in changes
                return updated
        return found
    saved = dict(insert_booking(row))
    if not saved.get("booking_id"):
        again = _open_booking(row)
        if again and again.get("booking_id"):
            saved = dict(again)
    saved["already_open"] = False
    saved["headcount_updated"] = False
    saved["group_updated"] = False
    return saved


def _phrase_in(text: str, phrase: str) -> bool:
    if not phrase:
        return False
    start = 0
    while True:
        index = text.find(phrase, start)
        if index < 0:
            return False
        end = index + len(phrase)
        before_ok = index == 0 or text[index - 1].isspace()
        after_ok = end == len(text) or text[end].isspace()
        if before_ok and after_ok:
            return True
        start = index + 1


def _program_matches(utterance: str) -> list[tuple[dict, str]]:
    from services.supabase_client import list_villages
    from services.village_name_requests import village_names
    from services.village_programs import program_labels

    found: list[tuple[dict, str]] = []
    for village in list_villages():
        for label in program_labels(village):
            if _phrase_in(utterance, label):
                found.append((village, label))
    if not found:
        return []
    longest = max(len(label) for _, label in found)
    found = [(village, label) for village, label in found if len(label) == longest]
    named = [
        (village, label)
        for village, label in found
        if any(_phrase_in(utterance, name) for name in village_names(village))
    ]
    picked = named or found
    by_village: dict[str, tuple[dict, str]] = {}
    for village, label in picked:
        by_village[str(village.get("village_id"))] = (village, label)
    return list(by_village.values())


def accept_named_booking(user_id: str, utterance: str, params: dict) -> dict:
    """체험 이름이 한 마을에만 있으면 그 마을 대기 예약. 요청의 마을 번호는 쓰지 않는다."""
    text = utterance or ""
    visit_date = str(params.get("visit_date") or "").strip()
    if not visit_date:
        found = _DATE_IN_TEXT.search(text)
        visit_date = found.group(0) if found else ""
    raw = params.get("num_people")
    if raw in (None, ""):
        counted = _COUNT_IN_TEXT.search(text)
        raw = counted.group(1) if counted else ""
    if not visit_date or raw in (None, ""):
        return {"ok": False, "text": "방문일과 인원수를 입력해 주세요."}
    try:
        num_people = int(raw)
    except (TypeError, ValueError):
        return {"ok": False, "text": "인원수는 숫자로 입력해 주세요."}
    if num_people < 1:
        return {"ok": False, "text": "인원수는 숫자로 입력해 주세요."}
    matches = _program_matches(text)
    if not matches:
        return {
            "ok": False,
            "text": "예약은 체험 이름, 날짜, 인원을 한 문장에 넣어 주세요. 예: 조개잡이 2026-11-01 30명",
        }
    if len(matches) > 1:
        return {
            "ok": False,
            "text": "같은 체험 이름이 여러 마을에 있습니다. 마을 이름을 같이 말해 주세요.",
        }
    village, label = matches[0]
    from services.field_changes import has_price_table
    from services.guest_book import bookable_names

    if has_price_table(str(village.get("village_id") or "")) and label not in bookable_names(village):
        return {"ok": False, "text": "이 체험은 지금은 예약할 수 없습니다."}
    from services.demo_data import DEMO_VILLAGE_ID
    from services.demo_role import persona_of

    if str(village.get("village_id") or "") == DEMO_VILLAGE_ID and not persona_of(user_id):
        return {"ok": False, "text": "이 체험은 지금은 예약할 수 없습니다."}
    from services.kakao_params import parse_spoken_time, parse_sys_time

    visit_time = parse_sys_time(params.get("visit_time")) or parse_spoken_time(text)
    saved = create_booking(
        village_id=str(village["village_id"]),
        customer_kakao_id=user_id,
        visit_date=visit_date,
        num_people=num_people,
        program_label=label,
        visit_time=visit_time,
    )
    if not saved.get("booking_id"):
        return {"ok": False, "text": "예약을 접수하지 못했습니다. 다시 눌러 주세요."}
    from services.demo_role import mark_guest_demo

    mark_guest_demo(user_id, saved.get("booking_id"))
    return {"ok": True, "booking": saved}


def get_booking_by_id(booking_id: int | str) -> dict | None:
    try:
        bid = int(booking_id)
    except (TypeError, ValueError):
        return None
    rows = list_bookings(booking_id=bid)
    return rows[0] if rows else None


def update_booking_status(booking_id: int | str, status: str) -> dict | None:
    """대기 예약만 승인·거절로 바꾼다. 이미 끝난 예약은 그대로 돌려준다."""
    try:
        bid = int(booking_id)
    except (TypeError, ValueError):
        return None
    current = get_booking_by_id(bid)
    if not current:
        return None
    if str(current.get("status") or "") != "pending":
        unchanged = dict(current)
        unchanged["unchanged"] = True
        return unchanged
    saved = save_booking_status(bid, status)
    if not saved:
        return None
    saved = dict(saved)
    saved["unchanged"] = False
    return saved


def _booking_id(booking_id: int | str) -> int | None:
    try:
        return int(booking_id)
    except (TypeError, ValueError):
        return None


def save_booking_proposal(booking_id: int | str, visit_date: str, visit_time: str) -> dict | None:
    """대기 예약에 제안 일시만 덮어쓴다. 방문 일시와 상태는 그대로다."""
    bid = _booking_id(booking_id)
    if bid is None:
        return None
    return update_booking(
        bid,
        {"proposed_visit_date": visit_date, "proposed_visit_time": visit_time},
    )


def clear_booking_proposal(booking_id: int | str) -> dict | None:
    bid = _booking_id(booking_id)
    if bid is None:
        return None
    return update_booking(bid, {"proposed_visit_date": None, "proposed_visit_time": None})


def apply_booking_proposal(booking_id: int | str) -> dict | None:
    """제안 일시를 방문 일시로 옮기고 제안 칸을 비운다. 상태는 바꾸지 않는다."""
    bid = _booking_id(booking_id)
    if bid is None:
        return None
    row = get_booking_by_id(bid)
    if not row:
        return None
    day = str(row.get("proposed_visit_date") or "")[:10]
    clock = str(row.get("proposed_visit_time") or "")[:5]
    if not day or not clock:
        return None
    return update_booking(
        bid,
        {
            "visit_date": day,
            "visit_time": clock,
            "proposed_visit_date": None,
            "proposed_visit_time": None,
        },
    )


def list_bookings_for_village(village_id: str) -> list[dict]:
    return list_bookings(village_id=village_id)


def list_bookings_for_operator(user_id: str) -> list[dict]:
    """운영자 발화 `예약 현황`. 마을 운영자만 조회한다."""
    from services.auth import resolve_kakao_role, scoped_village_id

    if resolve_kakao_role(user_id).get("role") == "program":
        raise PermissionError("village operator required")
    from services.demo_role import rows_for_demo_viewer

    return rows_for_demo_viewer(list_bookings_for_village(scoped_village_id(user_id)), user_id)


def list_my_bookings(user_id: str) -> list[dict]:
    """관광객 발화 `내 예약`. customer_kakao_id가 요청자인 행만."""
    return list_bookings(customer_kakao_id=user_id)


_STATUS_LABEL = {"pending": "대기", "confirmed": "승인", "rejected": "거절"}


def _total_sentence(saved: dict) -> str:
    from services.field_changes import line_total, won

    amount = line_total(saved.get("village_id"), saved.get("program_label"), saved.get("num_people"))
    if amount is None:
        return ""
    return f" {saved.get('num_people')}명 {won(amount)}."


def booking_receipt_text(saved: dict, link: str) -> tuple[str, str]:
    """카카오 답. 새 접수, 인원 수정, 이미 있는 예약을 구분하고 상태 주소를 붙인다."""
    number = saved.get("booking_id")
    label = _STATUS_LABEL.get(saved.get("status"), "대기")
    total = _total_sentence(saved)
    if saved.get("headcount_updated"):
        title = "예약 인원을 고쳤습니다"
        body = f"예약번호 {number}번 인원을 {saved.get('num_people')}명으로 고쳤습니다.{total}"
    elif saved.get("already_open"):
        title = "이미 접수된 예약입니다"
        body = f"예약번호 {number}번은 이미 {label} 상태입니다.{total}"
    else:
        title = "예약이 접수되었습니다"
        body = f"예약번호 {number}번 대기로 접수되었습니다.{total}"
    if link:
        body = f"{body} 진행 상태는 이 주소에서 볼 수 있습니다. {link}"
    return title, body


def guest_booking_reply(saved: dict) -> tuple[str, str]:
    """새 예약만 운영자에게 알리고, 손님 답에는 상태 링크를 넣는다."""
    from services.guest_book import issue_guest_book_link
    from services.kakao_client import notify_booking_received

    if not saved.get("already_open"):
        notify_booking_received(saved)
    link = issue_guest_book_link(
        str(saved.get("customer_kakao_id") or ""),
        str(saved.get("village_id") or ""),
    )
    return booking_receipt_text(saved, link)


def booking_summary(row: dict) -> str:
    """예약 한 줄. 시간이 있으면 날짜 뒤에 붙인다. 열린 제안이 있으면 그 일시를 덧붙인다."""
    label = _STATUS_LABEL.get(row.get("status"), row.get("status"))
    when = str(row.get("visit_date") or "")[:10]
    clock = str(row.get("visit_time") or "").strip()[:5]
    if clock:
        when = f"{when} {clock}".strip()
    people = f"{row.get('num_people')}명"
    group = _clean_group(row.get("group_name"))
    party = f"{group} {people}" if group else people
    line = f"{row.get('booking_id')}번 {label} {when} {party}"
    from services.field_changes import line_total, won

    amount = line_total(row.get("village_id"), row.get("program_label"), row.get("num_people"))
    if amount is not None:
        line = f"{line} {won(amount)}"
    offered = str(row.get("proposed_visit_date") or "")[:10]
    if offered:
        offered_clock = str(row.get("proposed_visit_time") or "").strip()[:5]
        if offered_clock:
            offered = f"{offered} {offered_clock}"
        line = f"{line} 변경 제안 {offered}"
    return line


def format_booking_lines(rows: list[dict]) -> str:
    if not rows:
        return "예약이 없습니다."
    return " ".join(booking_summary(row) for row in rows)


_SEOUL = timezone(timedelta(hours=9))
_WEEK_STATUS = re.compile(r"예약 현황(?: (\d{4}-\d{2}-\d{2}))?")
_WEEK_SHIFT = {"이번주": 0, "이전주": -1, "다음주": 1}


def seoul_today() -> date:
    return datetime.now(_SEOUL).date()


def _flat_week_text(utterance: str) -> str:
    return "".join((utterance or "").split())


def _week_phrase(utterance: str) -> tuple[int, str] | None:
    """이번·이전·다음 주. 뒤에 날짜가 있으면 그 문자열을 돌려준다."""
    text = " ".join((utterance or "").split())
    flat = _flat_week_text(text)
    for word, shift in _WEEK_SHIFT.items():
        if flat == word:
            return shift, ""
        spaced = f"{word[:-1]} 주"
        if text.startswith(spaced + " "):
            return shift, text[len(spaced) + 1 :]
        if flat.startswith(word) and len(flat) > len(word):
            return shift, flat[len(word) :]
    return None


def is_week_status_utterance(utterance: str) -> bool:
    """예약 현황, 날짜가 붙은 예약 현황, 이번 주·이전 주·다음 주."""
    text = " ".join((utterance or "").split())
    flat = _flat_week_text(text)
    if flat in {"예약현황", "예약현황조회"}:
        return True
    found = _WEEK_STATUS.fullmatch(text)
    if found:
        return True
    phrase = _week_phrase(text)
    if phrase is None:
        return False
    _shift, rest = phrase
    if not rest:
        return True
    try:
        date.fromisoformat(rest)
    except ValueError:
        return False
    return True


def status_week_anchor(utterance: str, today: date | None = None, user_id: str = "") -> date:
    """보여 줄 주의 하루. 이번 주와 예약 현황은 서울 오늘, 이전·다음은 방금 본 주에서 이동한다."""
    day = today or seoul_today()
    text = " ".join((utterance or "").split())
    flat = _flat_week_text(text)
    if flat in {"예약현황", "예약현황조회"}:
        return day
    dated = _WEEK_STATUS.fullmatch(text)
    if dated and dated.group(1):
        try:
            return date.fromisoformat(dated.group(1))
        except ValueError:
            return day
    phrase = _week_phrase(text)
    if phrase is None:
        return day
    shift, rest = phrase
    if rest:
        try:
            return date.fromisoformat(rest)
        except ValueError:
            return day
    if shift == 0:
        return day
    start, _end = week_bounds(_shown_week.get(user_id, day))
    return start + timedelta(days=7 * shift)


def remember_shown_week(user_id: str, anchor: date) -> None:
    if user_id:
        _shown_week[user_id] = week_bounds(anchor)[0]


def week_bounds(day: date) -> tuple[date, date]:
    """달력 머리글과 같이 일요일부터 토요일까지."""
    start = day - timedelta(days=(day.weekday() + 1) % 7)
    return start, start + timedelta(days=6)


def _visit_day(row: dict) -> date | None:
    try:
        return date.fromisoformat(str(row.get("visit_date") or "")[:10])
    except ValueError:
        return None


def _booking_sort_key(row: dict) -> tuple:
    try:
        number = int(row.get("booking_id") or 0)
    except (TypeError, ValueError):
        number = 0
    return (str(row.get("visit_date") or "")[:10], str(row.get("visit_time") or "").strip()[:5], number)


def bookings_in_week(rows: list[dict], anchor: date) -> tuple[date, date, list[dict]]:
    start, end = week_bounds(anchor)
    chosen = [row for row in rows if (day := _visit_day(row)) is not None and start <= day <= end]
    return start, end, sorted(chosen, key=_booking_sort_key)


def week_status_text(rows: list[dict], anchor: date) -> str:
    start, end, chosen = bookings_in_week(rows, anchor)
    span = f"{start.isoformat()}부터 {end.isoformat()}까지"
    if not chosen:
        return f"{span} 예약이 없습니다."
    return f"{span}. " + " ".join(booking_summary(row) for row in chosen)


def week_nav_replies(anchor: date) -> list[dict]:
    """버튼 문장은 오픈빌더에 그대로 넣을 수 있는 이번 주, 이전 주, 다음 주다."""
    return [
        {"label": "이전 주", "action": "message", "messageText": "이전 주"},
        {"label": "이번 주", "action": "message", "messageText": "이번 주"},
        {"label": "다음 주", "action": "message", "messageText": "다음 주"},
    ]


def bookings_for_operator_view(operator: dict) -> list[dict]:
    """마을 운영자는 마을 예약, 체험 담당은 맡은 체험 예약만."""
    from services.program_groups import assigned_program_keys

    from services.demo_role import without_marked_bookings

    rows = without_marked_bookings(list_bookings_for_village(str(operator.get("village_id") or "")))
    if str(operator.get("role") or "village") == "program":
        keys = assigned_program_keys(operator)
        return [row for row in rows if row.get("program_key") and row.get("program_key") in keys]
    return rows


def month_booking_summary(rows: list[dict], today: date | None = None) -> str:
    """서울 오늘이 들어 있는 달의 대기·승인·거절 건수."""
    day = today or seoul_today()
    counts = {"pending": 0, "confirmed": 0, "rejected": 0}
    for row in rows:
        visit = _visit_day(row)
        if visit is None or (visit.year, visit.month) != (day.year, day.month):
            continue
        status = str(row.get("status") or "")
        if status in counts:
            counts[status] += 1
    return (
        f"{day.year}년 {day.month}월 예약 "
        f"대기 {counts['pending']}건 승인 {counts['confirmed']}건 거절 {counts['rejected']}건"
    )


def _display_trust_score(village: dict) -> float:
    from services.trust_score import shown_trust_score

    return shown_trust_score(village)


def _village_rank(village_id: str, villages: list[dict]) -> dict:
    scored = [
        {"village_id": row.get("village_id"), "trust_score": _display_trust_score(row)}
        for row in villages
    ]
    mine = next((row for row in scored if row["village_id"] == village_id), None)
    if mine is None:
        return {
            "total_villages": len(villages),
            "trust_rank": None,
            "trust_score": None,
            "rank_message": "공개 마을 목록에서 이 마을을 찾지 못했습니다.",
        }
    higher = sum(1 for row in scored if row["trust_score"] > mine["trust_score"])
    return {
        "total_villages": len(villages),
        "trust_rank": higher + 1,
        "trust_score": mine["trust_score"],
        "rank_message": None,
    }


def get_public_dashboard_summary() -> dict:
    from services.supabase_client import list_public_villages

    villages = list_public_villages()
    top = sorted(
        [
            {
                "village_name": v.get("village_name"),
                "trust_score": _display_trust_score(v),
            }
            for v in villages
        ],
        key=lambda x: x["trust_score"],
        reverse=True,
    )[:5]
    return {
        "total_villages": len(villages),
        "top_trusted_villages": top,
    }


def _without_customer_kakao_id(row: dict) -> dict:
    visible = dict(row)
    visible.pop("customer_kakao_id", None)
    return visible


def _villages_for_operator_rank(village_id: str) -> list[dict]:
    """공개 목록에 담당 마을이 없으면 그 1건만 순위 계산에 보탠다."""
    from services.supabase_client import get_village_by_id, list_public_villages

    villages = list_public_villages()
    if any(row.get("village_id") == village_id for row in villages):
        return villages
    own = get_village_by_id(village_id)
    if own is None:
        return villages
    return [*villages, own]


def _rating_value(row: dict) -> float | None:
    raw = row.get("rating")
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _average_rating(reviews: list[dict]) -> float | None:
    ratings = [value for row in reviews if (value := _rating_value(row)) is not None]
    if not ratings:
        return None
    return round(sum(ratings) / len(ratings), 1)


def get_operator_dashboard_summary(operator: dict) -> dict:
    from services.review import list_reviews_for_village
    from services.supabase_client import get_village_by_id

    village_id = operator["village_id"]
    village = get_village_by_id(village_id) or {}
    village_bookings = list_bookings_for_village(village_id)
    pending = [b for b in village_bookings if b["status"] == "pending"]
    confirmed = [b for b in village_bookings if b["status"] == "confirmed"]
    rejected = [b for b in village_bookings if b["status"] == "rejected"]
    reviews = list_reviews_for_village(village_id)
    rank = _village_rank(village_id, _villages_for_operator_rank(village_id))
    return {
        "village_id": village_id,
        "village_name": village.get("village_name"),
        "sigungu": village.get("sigungu"),
        "grade": village.get("grade"),
        "total_bookings": len(village_bookings),
        "pending_bookings": len(pending),
        "confirmed_bookings": len(confirmed),
        "rejected_bookings": len(rejected),
        "review_count": len(reviews),
        "average_rating": _average_rating(reviews),
        "recent_bookings": [_without_customer_kakao_id(row) for row in village_bookings[-5:]],
        "recent_reviews": [_without_customer_kakao_id(row) for row in reviews],
        "total_villages": rank["total_villages"],
        "trust_rank": rank["trust_rank"],
        "trust_score": rank["trust_score"],
        "rank_message": rank["rank_message"],
    }
