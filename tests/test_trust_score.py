from services.trust_score import calculate_trust_score


def test_score_with_grade_and_recent_data_and_high_rating(sample_village_for_trust_score):
    score = calculate_trust_score(sample_village_for_trust_score)
    assert score >= 80


def test_score_without_grade_is_lower():
    with_grade = calculate_trust_score({"grade": "으뜸촌", "synced_days_ago": 5, "average_rating": 4.5})
    without_grade = calculate_trust_score({"grade": None, "synced_days_ago": 5, "average_rating": 4.5})
    assert without_grade < with_grade


def test_score_decreases_with_stale_data():
    fresh = calculate_trust_score({"grade": "으뜸촌", "synced_days_ago": 1, "average_rating": 4.0})
    stale = calculate_trust_score({"grade": "으뜸촌", "synced_days_ago": 200, "average_rating": 4.0})
    assert stale < fresh


def test_score_is_deterministic(sample_village_for_trust_score):
    score1 = calculate_trust_score(sample_village_for_trust_score)
    score2 = calculate_trust_score(sample_village_for_trust_score)
    assert score1 == score2


def test_score_within_valid_range(sample_village_for_trust_score):
    score = calculate_trust_score(sample_village_for_trust_score)
    assert 0 <= score <= 100


def test_score_handles_no_reviews():
    score = calculate_trust_score({"grade": None, "synced_days_ago": 3, "average_rating": None})
    assert isinstance(score, (int, float))


def test_synced_at_age_lowers_score_without_synced_days_ago():
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    fresh = calculate_trust_score({"grade": "으뜸촌", "synced_at": now.isoformat()})
    stale = calculate_trust_score(
        {"grade": "으뜸촌", "synced_at": (now - timedelta(days=200)).isoformat()}
    )
    assert stale < fresh


def test_missing_sync_time_does_not_grant_freshness_points():
    score = calculate_trust_score({"grade": None, "average_rating": None})
    assert score == 20
