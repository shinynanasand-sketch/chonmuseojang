"""예약 생성/조회/상태변경."""

from services.supabase_client import insert_booking, list_bookings, reset_booking_store, save_booking_status


def reset_bookings() -> None:
    reset_booking_store()


def create_booking(
    village_id: str,
    customer_kakao_id: str,
    visit_date: str,
    num_people: int,
    customer_name: str | None = None,
) -> dict:
    return insert_booking(
        {
            "village_id": village_id,
            "customer_kakao_id": customer_kakao_id,
            "customer_name": customer_name,
            "visit_date": visit_date,
            "num_people": num_people,
            "status": "pending",
        }
    )


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
    """운영자 발화 `예약 현황`. 관광객이면 호출하지 않는다."""
    from services.auth import scoped_village_id

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


def get_operator_dashboard_summary(operator: dict) -> dict:
    from services.review import list_reviews_for_village
    from services.supabase_client import list_public_villages

    village_id = operator["village_id"]
    village_bookings = list_bookings_for_village(village_id)
    pending = [b for b in village_bookings if b["status"] == "pending"]
    reviews = list_reviews_for_village(village_id)
    rank = _village_rank(village_id, list_public_villages())
    return {
        "village_id": village_id,
        "total_bookings": len(village_bookings),
        "pending_bookings": len(pending),
        "recent_bookings": [_without_customer_kakao_id(row) for row in village_bookings[-5:]],
        "recent_reviews": [_without_customer_kakao_id(row) for row in reviews],
        "total_villages": rank["total_villages"],
        "trust_rank": rank["trust_rank"],
        "trust_score": rank["trust_score"],
        "rank_message": rank["rank_message"],
    }
