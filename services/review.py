"""후기 생성/조회, 감성분석 연동."""

_reviews: list[dict] = []
_review_id_counter = 1


def create_review(
    village_id: str,
    booking_id: int | str,
    customer_kakao_id: str,
    comment: str,
    rating: int | None = None,
    sentiment: str | None = None,
) -> dict:
    global _review_id_counter
    review = {
        "review_id": _review_id_counter,
        "village_id": village_id,
        "booking_id": int(booking_id),
        "customer_kakao_id": customer_kakao_id,
        "comment": comment,
        "rating": rating,
        "sentiment": sentiment,
    }
    _review_id_counter += 1
    _reviews.append(review)
    return review


def analyze_sentiment(text: str) -> str:
    from services.llm_provider import get_llm_provider

    try:
        llm = get_llm_provider()
        result = llm.generate("감성을 '긍정' 또는 '부정' 한 단어로만 답하세요.", text)
        if "부정" in result:
            return "부정"
        return "긍정"
    except Exception:
        return "긍정"
