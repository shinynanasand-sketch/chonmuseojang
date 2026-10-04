"""예약·후기는 Supabase에 저장되고, 조회는 village_id 또는 customer_kakao_id로만 제한된다."""

from types import SimpleNamespace

import pytest

from services.booking import (
    create_booking,
    list_bookings_for_village,
    list_my_bookings,
    update_booking_status,
)
from services.review import create_review, list_reviews_for_village


class _Query:
    def __init__(self, table_name: str, store: dict, op: str | None = None, payload: dict | None = None):
        self.table_name = table_name
        self.store = store
        self.op = op
        self.payload = payload
        self.filters: list[tuple[str, object]] = []
        self.sort_key: str | None = None

    def insert(self, payload: dict):
        return _Query(self.table_name, self.store, op="insert", payload=dict(payload))

    def select(self, *_columns: str):
        cloned = _Query(self.table_name, self.store, op="select")
        cloned.filters = list(self.filters)
        return cloned

    def update(self, payload: dict):
        cloned = _Query(self.table_name, self.store, op="update", payload=dict(payload))
        cloned.filters = list(self.filters)
        return cloned

    def eq(self, key: str, value: object):
        cloned = _Query(self.table_name, self.store, op=self.op, payload=self.payload)
        cloned.filters = [*self.filters, (key, value)]
        cloned.sort_key = self.sort_key
        return cloned

    def order(self, key: str, *_args, **_kwargs):
        cloned = _Query(self.table_name, self.store, op=self.op, payload=self.payload)
        cloned.filters = list(self.filters)
        cloned.sort_key = key
        return cloned

    def limit(self, _count: int):
        return self

    def execute(self):
        rows = self.store.setdefault(self.table_name, [])
        if self.op == "insert":
            saved = dict(self.payload or {})
            id_key = "booking_id" if self.table_name == "bookings" else "review_id"
            if id_key not in saved:
                saved[id_key] = max((row.get(id_key) or 0) for row in rows) + 1 if rows else 1
            rows.append(saved)
            return SimpleNamespace(data=[dict(saved)])
        matched = [
            row
            for row in rows
            if all(row.get(key) == value for key, value in self.filters)
        ]
        if self.op == "update":
            for row in matched:
                row.update(self.payload or {})
            return SimpleNamespace(data=[dict(row) for row in matched])
        if self.sort_key:
            matched = sorted(matched, key=lambda row: row.get(self.sort_key) or 0)
        return SimpleNamespace(data=[dict(row) for row in matched])


class FakeSupabase:
    def __init__(self):
        self.tables: dict[str, list] = {}

    def table(self, name: str) -> _Query:
        return _Query(name, self.tables)


@pytest.fixture
def supabase_bookings(monkeypatch):
    client = FakeSupabase()
    monkeypatch.setattr("services.supabase_client.get_supabase_client", lambda: client)
    return client


def test_create_booking_inserts_into_supabase(supabase_bookings):
    created = create_booking("V001", "cust-a", "2026-10-04", 2, customer_name="김")
    stored = supabase_bookings.tables.get("bookings", [])
    assert stored
    assert stored[0]["village_id"] == "V001"
    assert stored[0]["status"] == "pending"
    assert created["booking_id"] == stored[0]["booking_id"]


def test_list_bookings_for_village_reads_only_that_village(supabase_bookings):
    supabase_bookings.tables["bookings"] = [
        {
            "booking_id": 1,
            "village_id": "V001",
            "customer_kakao_id": "a",
            "visit_date": "2026-10-01",
            "num_people": 2,
            "status": "pending",
        },
        {
            "booking_id": 2,
            "village_id": "V002",
            "customer_kakao_id": "b",
            "visit_date": "2026-10-02",
            "num_people": 1,
            "status": "pending",
        },
    ]
    rows = list_bookings_for_village("V001")
    assert [row["booking_id"] for row in rows] == [1]
    assert {row["village_id"] for row in rows} == {"V001"}


def test_update_booking_status_persists_in_supabase(supabase_bookings):
    supabase_bookings.tables["bookings"] = [
        {
            "booking_id": 4,
            "village_id": "V001",
            "customer_kakao_id": "a",
            "visit_date": "2026-10-01",
            "num_people": 2,
            "status": "pending",
        }
    ]
    updated = update_booking_status(4, "confirmed")
    assert updated is not None
    assert updated["status"] == "confirmed"
    assert supabase_bookings.tables["bookings"][0]["status"] == "confirmed"


def test_list_my_bookings_reads_only_that_customer(supabase_bookings):
    supabase_bookings.tables["bookings"] = [
        {
            "booking_id": 1,
            "village_id": "V001",
            "customer_kakao_id": "me",
            "visit_date": "2026-10-01",
            "num_people": 2,
            "status": "pending",
        },
        {
            "booking_id": 2,
            "village_id": "V002",
            "customer_kakao_id": "other",
            "visit_date": "2026-10-02",
            "num_people": 1,
            "status": "confirmed",
        },
    ]
    rows = list_my_bookings("me")
    assert [row["booking_id"] for row in rows] == [1]
    assert {row["customer_kakao_id"] for row in rows} == {"me"}


def test_create_review_inserts_into_supabase(supabase_bookings):
    created = create_review(
        "V001",
        1,
        "cust-a",
        "좋았어요",
        rating=5,
        sentiment="긍정",
    )
    stored = supabase_bookings.tables.get("reviews", [])
    assert stored
    assert stored[0]["village_id"] == "V001"
    assert stored[0]["comment"] == "좋았어요"
    assert created["review_id"] == stored[0]["review_id"]


def test_list_reviews_for_village_excludes_other_village(supabase_bookings):
    supabase_bookings.tables["reviews"] = [
        {"review_id": 1, "village_id": "V001", "comment": "좋았어요"},
        {"review_id": 2, "village_id": "V002", "comment": "별로였어요"},
    ]
    rows = list_reviews_for_village("V001")
    assert [row["review_id"] for row in rows] == [1]
    assert {row["village_id"] for row in rows} == {"V001"}
