import pytest

from services.auth import register_operator
from services.supabase_client import (
    delete_operator_by_kakao_id,
    detach_operators_for_village,
    list_villages,
    restore_operators,
    set_registration_code,
    upsert_villages,
)


@pytest.fixture
def sample_village_with_registration_code():
    village = {
        "village_id": "V001",
        "village_name": "예시 갯벌마을",
        "registration_code": "GB-001",
    }
    detached = detach_operators_for_village(village["village_id"])
    upsert_villages([village])
    set_registration_code(village["village_id"], village["registration_code"], village)
    yield village
    delete_operator_by_kakao_id("new_owner_kakao")
    restore_operators(detached)


def test_register_operator_with_valid_code_inserts_row(sample_village_with_registration_code):
    utterance = "등록 예시 갯벌마을 GB-001"
    result = register_operator("new_owner_kakao", utterance)
    assert result["ok"] is True
    assert result["village_id"] == sample_village_with_registration_code["village_id"]


def test_register_operator_without_prefix_inserts_row(sample_village_with_registration_code):
    result = register_operator("new_owner_kakao", "예시 갯벌마을 GB-001")
    assert result["ok"] is True
    assert result["village_id"] == sample_village_with_registration_code["village_id"]


def test_register_operator_rejects_wrong_code(sample_village_with_registration_code):
    result = register_operator("new_owner_kakao", "등록 예시 갯벌마을 WRONG")
    assert result == {"ok": False, "reason": "code_mismatch"}


def test_same_code_on_sido_copies_registers_one_village():
    upsert_villages(
        [
            {
                "village_id": "OLD",
                "village_name": "소포마을",
                "sigungu": "진도군",
                "address": "전라남도 진도군",
            },
            {
                "village_id": "NEW",
                "village_name": "소포마을",
                "sigungu": "진도군",
                "address": "전남광주통합특별시 진도군",
            },
        ]
    )
    set_registration_code("OLD", "SP-010")
    set_registration_code("NEW", "SP-010")
    result = register_operator("sopo_owner", "등록 소포마을 SP-010")
    assert result == {"ok": True, "village_id": "NEW"}
    delete_operator_by_kakao_id("sopo_owner")


def test_same_name_in_two_sigungu_needs_sigungu_in_utterance():
    upsert_villages(
        [
            {"village_id": "DAM", "village_name": "학동마을", "sigungu": "담양군"},
            {"village_id": "GO", "village_name": "학동마을", "sigungu": "고흥군"},
        ]
    )
    set_registration_code("DAM", "DM-011")
    set_registration_code("GO", "GH-012")
    assert register_operator("owner_short", "등록 학동마을 DM-011") == {
        "ok": False,
        "reason": "village_not_found",
    }
    result = register_operator("owner_dam", "등록 담양군 학동마을 DM-011")
    assert result == {"ok": True, "village_id": "DAM"}
    assert register_operator("owner_bad", "등록 담양군 학동마을 GH-012") == {
        "ok": False,
        "reason": "code_mismatch",
    }
    delete_operator_by_kakao_id("owner_dam")


def test_sync_keeps_existing_registration_code(sample_village_with_registration_code):
    upsert_villages(
        [{"village_id": "V001", "village_name": "예시 갯벌마을", "sigungu": "신안군"}]
    )
    rows = [row for row in list_villages() if row["village_id"] == "V001"]
    assert rows[0]["registration_code"] == "GB-001"


class _Table:
    def __init__(self, name: str, store: dict, reads: list):
        self.name = name
        self.store = store
        self.reads = reads
        self.filters: list[tuple[str, object]] = []
        self.columns = "*"
        self.op = "select"
        self.payload = None
        self.limited = None

    def select(self, columns="*"):
        self.op = "select"
        self.columns = columns
        return self

    def eq(self, key: str, value: object):
        self.filters.append((key, value))
        return self

    def limit(self, count: int):
        self.limited = count
        return self

    def insert(self, payload: dict):
        self.op = "insert"
        self.payload = dict(payload)
        return self

    def execute(self):
        if self.name == "villages_cache" and self.op == "select":
            self.reads.append(
                {"columns": self.columns, "filters": list(self.filters), "limit": self.limited}
            )
        rows = self.store.setdefault(self.name, [])
        if self.op == "insert":
            rows.append(dict(self.payload or {}))
            return type("Result", (), {"data": [dict(self.payload or {})]})()
        matched = [
            row for row in rows if all(row.get(key) == value for key, value in self.filters)
        ]
        if self.limited is not None:
            matched = matched[: self.limited]
        return type("Result", (), {"data": [dict(row) for row in matched]})()


class _Client:
    def __init__(self):
        self.store: dict[str, list] = {
            "villages_cache": [
                {
                    "village_id": "V008",
                    "village_name": "예시 갯벌마을",
                    "sigungu": "신안군",
                    "registration_code": "GB-001",
                },
                {
                    "village_id": "OTHER",
                    "village_name": "다른마을",
                    "registration_code": "XX-002",
                },
            ]
        }
        self.reads: list = []

    def table(self, name: str) -> _Table:
        return _Table(name, self.store, self.reads)


def test_register_with_village_id_does_not_scan_all_villages(test_client, monkeypatch):
    client = _Client()
    monkeypatch.setattr("services.supabase_client.get_supabase_client", lambda: client)
    response = test_client.post(
        "/kakao/ask",
        json={
            "intent": {"name": "운영자등록"},
            "userRequest": {"utterance": "예시 갯벌마을 GB-001", "user": {"id": "fresh_owner"}},
            "action": {"params": {"village_id": "V008", "registration_code": "GB-001"}},
        },
    )
    assert response.status_code == 200
    assert "등록 완료" in response.text
    assert client.reads
    assert all(read["filters"] for read in client.reads)
    assert all(("village_id", "V008") in read["filters"] for read in client.reads)
    assert all(read["limit"] == 1 for read in client.reads)


def test_spoken_registration_looks_up_village_name(monkeypatch):
    client = _Client()
    monkeypatch.setattr("services.supabase_client.get_supabase_client", lambda: client)
    result = register_operator("spoken_owner", "예시 갯벌마을 GB-001")
    assert result == {"ok": True, "village_id": "V008"}
    assert client.reads
    assert all(read["filters"] for read in client.reads)
    assert any(("village_name", "예시 갯벌마을") in read["filters"] for read in client.reads)


def test_recommend_list_uses_needed_columns_and_reuses_them(monkeypatch):
    calls = {"n": 0}

    class _Rows:
        def select(self, columns="*"):
            self.columns = columns
            return self

        def execute(self):
            calls["n"] += 1
            calls["columns"] = self.columns
            return type(
                "Result",
                (),
                {
                    "data": [
                        {
                            "village_id": "A",
                            "village_name": "갯벌마을",
                            "sido": "전라남도",
                            "sigungu": "신안군",
                            "program_type": "갯벌체험",
                        }
                    ]
                },
            )()

    class _RowsClient:
        def table(self, _name: str) -> _Rows:
            return _Rows()

    monkeypatch.setattr("services.supabase_client._use_supabase", lambda: True)
    monkeypatch.setattr("services.supabase_client.get_supabase_client", lambda: _RowsClient())
    from services.supabase_client import list_recommend_villages

    first = list_recommend_villages()
    second = list_recommend_villages()
    assert first[0]["village_id"] == "A"
    assert second[0]["village_id"] == "A"
    assert calls["n"] == 1
    assert calls["columns"] != "*"
    assert "village_name" in calls["columns"]
    assert "registration_code" not in calls["columns"]


def test_supabase_client_is_cached_with_two_second_timeout(monkeypatch):
    import sys
    import types

    captured = {}

    class _Options:
        def __init__(self, **kwargs):
            captured["options"] = kwargs

    def _create(url, key, options=None):
        captured["url"] = url
        captured["key"] = key
        captured["options_obj"] = options
        return {"client": object()}

    fake = types.ModuleType("supabase")
    fake.ClientOptions = _Options
    fake.create_client = _create
    monkeypatch.setitem(sys.modules, "supabase", fake)
    monkeypatch.setattr("services.supabase_client._use_supabase", lambda: True)
    monkeypatch.setattr("services.supabase_client._client", None)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")
    from services.supabase_client import get_supabase_client

    first = get_supabase_client()
    second = get_supabase_client()
    assert first is second
    assert captured["options"]["postgrest_client_timeout"] == 2
    assert captured["options"]["storage_client_timeout"] == 2
