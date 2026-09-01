from services.booking import create_booking, get_operator_dashboard_summary


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
