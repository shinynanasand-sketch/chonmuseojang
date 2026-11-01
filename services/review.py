"""후기 생성/조회, 감성분석 연동."""

from services.supabase_client import get_review_for_booking, insert_review, list_reviews


def create_review(
    village_id: str,
    booking_id: int | str,
    customer_kakao_id: str,
    comment: str,
    rating: int | None = None,
    sentiment: str | None = None,
) -> dict:
    row = {
        "village_id": village_id,
        "booking_id": int(booking_id),
        "customer_kakao_id": customer_kakao_id,
        "comment": comment,
        "rating": rating,
    }
    if sentiment in ("긍정", "부정"):
        row["sentiment"] = sentiment
    return insert_review(row)


def list_reviews_for_village(village_id: str) -> list[dict]:
    return list_reviews(village_id=village_id)


def analyze_sentiment(text: str) -> str | None:
    """분명한 긍정·부정만 돌려준다. 실패하거나 판단이 없으면 저장하지 않는다."""
    from services.llm_provider import get_llm_provider

    if not (text or "").strip():
        return None
    try:
        llm = get_llm_provider()
        result = llm.generate("감성을 '긍정' 또는 '부정' 한 단어로만 답하세요.", text)
    except Exception:
        return None
    if "부정" in result:
        return "부정"
    if "긍정" in result:
        return "긍정"
    return None


def register_booking_review(
    booking_id: int,
    customer_kakao_id: str,
    comment: str,
    rating: int | None = None,
) -> dict:
    """본인 예약에 후기 한 건만 받는다. 없으면 예시 마을에 넣지 않는다."""
    from services.booking import get_booking_by_id
    from services.trust_score import recalculate_for_village

    existing = get_booking_by_id(booking_id)
    if not existing:
        return {"ok": False, "text": "예약을 찾은 뒤에 후기를 등록해 주세요."}
    if str(existing.get("customer_kakao_id") or "") != str(customer_kakao_id):
        return {"ok": False, "text": "이 예약의 후기만 등록할 수 있습니다."}
    prior = get_review_for_booking(int(booking_id))
    if prior:
        return {"ok": False, "text": "이미 등록된 후기입니다.", "duplicate": True}
    saved = create_review(
        village_id=str(existing["village_id"]),
        booking_id=booking_id,
        customer_kakao_id=customer_kakao_id,
        comment=comment,
        rating=rating,
        sentiment=analyze_sentiment(comment),
    )
    recalculate_for_village(str(existing["village_id"]))
    return {"ok": True, "review": saved}
