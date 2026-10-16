"""예약 생성/조회/상태변경."""

import re

from services.supabase_client import insert_booking, list_bookings, reset_booking_store, save_booking_status

_DATE_IN_TEXT = re.compile(r"\d{4}-\d{2}-\d{2}")
_COUNT_IN_TEXT = re.compile(r"(\d+)\s*명")


def reset_bookings() -> None:
    reset_booking_store()


def create_booking(
    village_id: str,
    customer_kakao_id: str,
    visit_date: str,
    num_people: int,
    customer_name: str | None = None,
    program_label: str | None = None,
) -> dict:
    row = {
        "village_id": village_id,
        "customer_kakao_id": customer_kakao_id,
        "customer_name": customer_name,
        "visit_date": visit_date,
        "num_people": num_people,
        "status": "pending",
    }
    label = (program_label or "").strip()
    if label:
        from services.village_programs import program_key

        row["program_label"] = label
        row["program_key"] = program_key(label)
    return insert_booking(row)


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
        if _phrase_in(utterance, str(village.get("village_name") or ""))
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
    saved = create_booking(
        village_id=str(village["village_id"]),
        customer_kakao_id=user_id,
        visit_date=visit_date,
        num_people=num_people,
        program_label=label,
    )
    return {"ok": True, "booking": saved}


def get_booking_by_id(booking_id: int | str) -> dict | None:
    try:
        bid = int(booking_id)
    except (TypeError, ValueError):
        return None
    rows = list_bookings(booking_id=bid)
    return rows[0] if rows else None


def update_booking_status(booking_id: int | str, status: str) -> dict | None:
    try:
        bid = int(booking_id)
    except (TypeError, ValueError):
        return None
    return save_booking_status(bid, status)


def list_bookings_for_village(village_id: str) -> list[dict]:
    return list_bookings(village_id=village_id)


def list_bookings_for_operator(user_id: str) -> list[dict]:
    """운영자 발화 `예약 현황`. 마을 운영자만 조회한다."""
    from services.auth import resolve_kakao_role, scoped_village_id

    if resolve_kakao_role(user_id).get("role") == "program":
        raise PermissionError("village operator required")
    return list_bookings_for_village(scoped_village_id(user_id))


def list_my_bookings(user_id: str) -> list[dict]:
    """관광객 발화 `내 예약`. customer_kakao_id가 요청자인 행만."""
    return list_bookings(customer_kakao_id=user_id)


_STATUS_LABEL = {"pending": "대기", "confirmed": "승인", "rejected": "거절"}


def format_booking_lines(rows: list[dict]) -> str:
    if not rows:
        return "예약이 없습니다."
    parts = []
    for row in rows:
        label = _STATUS_LABEL.get(row.get("status"), row.get("status"))
        parts.append(
            f"{row['booking_id']}번 {label} {row.get('visit_date')} {row.get('num_people')}명"
        )
    return " ".join(parts)


def _display_trust_score(village: dict) -> float:
    from services.trust_score import calculate_trust_score

    return calculate_trust_score(village)


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
