from services.booking import create_booking, get_operator_dashboard_summary
from services.review import create_review


def test_operator_dashboard_scoped_to_village(sample_operator_a):
    create_booking("V001", "c1", "2026-09-20", 2)
    summary = get_operator_dashboard_summary(sample_operator_a)
    assert summary["village_id"] == sample_operator_a["village_id"]
    assert "total_bookings" in summary
    assert "pending_bookings" in summary


def test_operator_dashboard_excludes_other_village_bookings(sample_operator_a, sample_operator_b):
    create_booking("V001", "c1", "2026-09-20", 2)
    create_booking("V002", "c2", "2026-09-21", 3)
    summary_a = get_operator_dashboard_summary(sample_operator_a)
    summary_b = get_operator_dashboard_summary(sample_operator_b)
    if summary_a.get("recent_bookings") and summary_b.get("recent_bookings"):
        ids_a = {b["booking_id"] for b in summary_a["recent_bookings"]}
        ids_b = {b["booking_id"] for b in summary_b["recent_bookings"]}
        assert ids_a.isdisjoint(ids_b)


def test_dashboard_without_auth_rejects_other_village_query(test_client):
    response = test_client.get("/api/operator/dashboard", params={"village_id": "V002"})
    assert response.status_code == 401


def test_bearer_login_sees_only_own_village_bookings_and_reviews(test_client):
    own = create_booking("V001", "kakao-hidden-a", "2026-10-04", 2)
    create_booking("V002", "kakao-hidden-b", "2026-10-05", 1)
    create_review("V001", own["booking_id"], "kakao-hidden-a", "좋았어요", rating=5, sentiment="긍정")
    create_review("V002", 99, "kakao-hidden-b", "다른 마을", rating=1, sentiment="부정")

    response = test_client.get(
        "/api/operator/dashboard",
        headers={"Authorization": "Bearer owner_v001"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["village_id"] == "V001"
    assert {row["village_id"] for row in body["recent_bookings"]} == {"V001"}
    assert {row["village_id"] for row in body["recent_reviews"]} == {"V001"}
    assert "kakao-hidden-a" not in response.text
    assert "다른 마을" not in response.text


def test_mismatched_village_query_is_forbidden(test_client):
    response = test_client.get(
        "/api/operator/dashboard",
        params={"village_id": "V002"},
        headers={"Authorization": "Bearer owner_v001"},
    )
    assert response.status_code == 403


def test_operator_sees_rank_without_other_village_bookings(test_client):
    from datetime import datetime, timedelta, timezone

    from services.supabase_client import upsert_villages

    now = datetime.now(timezone.utc)
    upsert_villages(
        [
            {
                "village_id": "V001",
                "village_name": "예시 갯벌마을",
                "sigungu": "신안군",
                "grade": "으뜸촌",
                "synced_at": now.isoformat(),
            },
            {
                "village_id": "V002",
                "village_name": "예시 무등마을",
                "sigungu": "북구",
                "synced_at": (now - timedelta(days=200)).isoformat(),
            },
        ]
    )
    create_booking("V002", "kakao-other", "2099-01-01", 9)

    response = test_client.get(
        "/api/operator/dashboard",
        headers={"Authorization": "Bearer owner_v001"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_villages"] == 2
    assert body["trust_rank"] == 1
    assert isinstance(body["trust_score"], (int, float))
    assert "2099-01-01" not in response.text


def test_home_nav_omits_operations_link(test_client):
    html = test_client.get("/").text
    assert "운영현황" not in html
    assert 'href="/dashboard"' not in html


def test_operator_page_asks_for_login_id_not_password(test_client):
    response = test_client.get("/operator")
    assert response.status_code == 200
    html = response.text
    assert 'type="password"' not in html
    assert 'name="login_id"' in html
    assert "내 마을" in html
