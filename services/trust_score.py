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


def recalculate_for_village(village_id: str) -> float:
    """후기 등록 후 마을 신뢰도 재계산 (스텁)."""
    from services.supabase_client import get_village_by_id

    village = get_village_by_id(village_id) or {}
    return calculate_trust_score(village)
