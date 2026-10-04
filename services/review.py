"""후기 생성/조회, 감성분석 연동."""

from services.supabase_client import insert_review, list_reviews


def create_review(
    village_id: str,
    booking_id: int | str,
    customer_kakao_id: str,
    comment: str,
    rating: int | None = None,
    sentiment: str | None = None,
) -> dict:
    return insert_review(
        {
            "village_id": village_id,
            "booking_id": int(booking_id),
            "customer_kakao_id": customer_kakao_id,
            "comment": comment,
            "rating": rating,
            "sentiment": sentiment,
        }
    )


def list_reviews_for_village(village_id: str) -> list[dict]:
    return list_reviews(village_id=village_id)


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
