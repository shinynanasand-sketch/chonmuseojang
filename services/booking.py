"""예약 생성/조회/상태변경."""

from datetime import date

_bookings: list[dict] = []
_booking_id_counter = 1


def _next_booking_id() -> int:
    global _booking_id_counter
    bid = _booking_id_counter
    _booking_id_counter += 1
    return bid


def reset_bookings() -> None:
    global _bookings, _booking_id_counter
    _bookings = []
    _booking_id_counter = 1


def create_booking(
    village_id: str,
    customer_kakao_id: str,
    visit_date: str,
    num_people: int,
    customer_name: str | None = None,
) -> dict:
    booking = {
        "booking_id": _next_booking_id(),
        "village_id": village_id,
        "customer_kakao_id": customer_kakao_id,
        "customer_name": customer_name,
        "visit_date": visit_date,
        "num_people": num_people,
        "status": "pending",
    }
    _bookings.append(booking)
    return booking


def get_booking_by_id(booking_id: int | str) -> dict | None:
    try:
        bid = int(booking_id)
    except (TypeError, ValueError):
        return None
    for booking in _bookings:
        if booking["booking_id"] == bid:
            return booking
    return None


def update_booking_status(booking_id: int | str, status: str) -> dict | None:
    booking = get_booking_by_id(booking_id)
    if not booking:
        return None
    booking["status"] = status
    return booking


def list_bookings_for_village(village_id: str) -> list[dict]:
    return [b for b in _bookings if b["village_id"] == village_id]


def get_public_dashboard_summary() -> dict:
    from services.supabase_client import list_villages
    from services.trust_score import calculate_trust_score

    villages = list_villages()
    top = sorted(
        [
            {
                "village_name": v.get("village_name"),
                "trust_score": v.get("trust_score") or calculate_trust_score(v),
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


def get_operator_dashboard_summary(operator: dict) -> dict:
    village_id = operator["village_id"]
    village_bookings = list_bookings_for_village(village_id)
    pending = [b for b in village_bookings if b["status"] == "pending"]
    return {
        "village_id": village_id,
        "total_bookings": len(village_bookings),
        "pending_bookings": len(pending),
        "recent_bookings": village_bookings[-5:],
    }
