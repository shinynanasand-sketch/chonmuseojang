def _days_from_synced_at(synced_at: object) -> int | None:
    from datetime import datetime, timezone

    if not synced_at:
        return None
    if isinstance(synced_at, datetime):
        moment = synced_at
    else:
        text = str(synced_at).strip().replace("Z", "+00:00")
        try:
            moment = datetime.fromisoformat(text)
        except ValueError:
            return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    elapsed = datetime.now(timezone.utc) - moment.astimezone(timezone.utc)
    return max(0, elapsed.days)


def _freshness_days(village: dict) -> int | None:
    if "synced_days_ago" in village and village.get("synced_days_ago") is not None:
        try:
            return int(village["synced_days_ago"])
        except (TypeError, ValueError):
            return None
    return _days_from_synced_at(village.get("synced_at"))


def _freshness_points(days: int | None) -> int:
    if days is None:
        return 0
    if days <= 30:
        return 20
    return max(0, 20 - (days - 30) // 10)


def calculate_trust_score(village: dict) -> float:
    """신뢰도 점수 계산 (FR-05)."""
    grade = village.get("grade")
    average_rating = village.get("average_rating")

    base = 40 if grade == "으뜸촌" else 20
    freshness = _freshness_points(_freshness_days(village))
    review_score = min(40, (average_rating or 0) * 8)

    total = base + freshness + review_score
    return max(0.0, min(100.0, float(total)))


def shown_trust_score(village: dict) -> float:
    """저장된 점수가 있으면 그 값을 쓴다. 0점도 계산값으로 바꾸지 않는다."""
    stored = village.get("trust_score")
    if stored is not None and stored != "":
        try:
            return float(stored)
        except (TypeError, ValueError):
            pass
    return calculate_trust_score(village)


def _average_rating(village_id: str) -> float | None:
    from services.review import list_reviews_for_village

    ratings: list[float] = []
    for row in list_reviews_for_village(village_id):
        raw = row.get("rating")
        if raw is None or str(raw).strip() == "":
            continue
        try:
            ratings.append(float(raw))
        except (TypeError, ValueError):
            continue
    if not ratings:
        return None
    return round(sum(ratings) / len(ratings), 2)


def recalculate_for_village(village_id: str) -> float:
    """별점 평균으로 신뢰도를 다시 계산해 마을 점수에 저장한다."""
    from services.supabase_client import get_village_by_id, update_village_fields

    village = dict(get_village_by_id(village_id) or {})
    average = _average_rating(village_id)
    village["average_rating"] = average
    score = calculate_trust_score(village)
    if get_village_by_id(village_id):
        update_village_fields(
            village_id,
            {"trust_score": score, "average_rating": average},
        )
    return score
