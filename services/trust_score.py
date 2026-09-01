def calculate_trust_score(village: dict) -> float:
    """신뢰도 점수 계산 (FR-05)."""
    grade = village.get("grade")
    synced_days_ago = village.get("synced_days_ago", 0) or 0
    average_rating = village.get("average_rating")

    base = 40 if grade == "으뜸촌" else 20
    freshness = 20 if synced_days_ago <= 30 else max(0, 20 - (synced_days_ago - 30) // 10)
    review_score = min(40, (average_rating or 0) * 8)

    total = base + freshness + review_score
    return max(0.0, min(100.0, float(total)))


def recalculate_for_village(village_id: str) -> float:
    """후기 등록 후 마을 신뢰도 재계산 (스텁)."""
    from services.supabase_client import get_village_by_id

    village = get_village_by_id(village_id) or {}
    return calculate_trust_score(village)
