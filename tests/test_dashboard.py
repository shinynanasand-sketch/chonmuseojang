from services.booking import get_public_dashboard_summary


def test_public_dashboard_counts_total_villages():
    summary = get_public_dashboard_summary()
    assert "total_villages" in summary
    assert isinstance(summary["total_villages"], int)


def test_public_dashboard_returns_top_trusted_villages_sorted():
    summary = get_public_dashboard_summary()
    scores = [v["trust_score"] for v in summary.get("top_trusted_villages", [])]
    assert scores == sorted(scores, reverse=True)
