from services.booking import create_booking, get_public_dashboard_summary
from services.review import register_booking_review
from services.supabase_client import upsert_villages
from services.trust_score import calculate_trust_score, shown_trust_score


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


def test_stored_zero_stays_zero():
    village = {"grade": "으뜸촌", "synced_days_ago": 1, "average_rating": 5, "trust_score": 0}
    assert shown_trust_score(village) == 0
    assert calculate_trust_score(village) > 0


def test_review_raises_the_stored_public_rank():
    upsert_villages(
        [
            {
                "village_id": "PDLOW",
                "village_name": "낮은마을",
                "sido": "전라남도",
                "sigungu": "신안군",
                "program_name": "산책",
            },
            {
                "village_id": "PDHIGH",
                "village_name": "높은마을",
                "sido": "전라남도",
                "sigungu": "해남군",
                "program_name": "갯벌",
            },
        ]
    )
    booking = create_booking("PDHIGH", "rank-guest", "2026-11-08", 2)
    saved = register_booking_review(booking["booking_id"], "rank-guest", "좋았다", rating=5)
    assert saved["ok"] is True
    top = get_public_dashboard_summary()["top_trusted_villages"]
    assert top[0]["village_name"] == "높은마을"
    assert top[0]["trust_score"] == 60


def test_recommend_keeps_stored_zero(test_client):
    upsert_villages(
        [
            {
                "village_id": "PDZERO",
                "village_name": "영점마을",
                "sido": "전라남도",
                "sigungu": "신안군",
                "program_name": "갯벌체험",
                "grade": "으뜸촌",
                "trust_score": 0,
            }
        ]
    )
    response = test_client.post("/api/recommend", json={"query": "갯벌체험"})
    assert response.status_code == 200
    match = next(row for row in response.json()["results"] if row["village_id"] == "PDZERO")
    assert match["trust_score"] == 0
