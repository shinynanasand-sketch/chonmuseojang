import pytest

from services.kakao_entity_export import (
    EntityExportError,
    build_registration_code_rows,
    build_village_name_rows,
    export_entity_csvs,
    expand_synonyms,
)


def test_expand_synonyms_keeps_name_then_alias_tokens():
    row = {
        "village_id": "V001",
        "village_name": " 예시 갯벌마을 ",
        "alias": " 갯벌마을 |갯벌 마을、 ,;조개마을",
    }
    assert expand_synonyms(row) == ["예시 갯벌마을", "갯벌마을", "갯벌 마을", "조개마을"]


def test_trailing_parentheses_become_two_synonyms():
    assert expand_synonyms({"village_name": "사곡마을(갯벌노을마을)"}) == ["사곡마을", "갯벌노을마을"]
    assert expand_synonyms({"village_name": "봉조농촌체험학교(봉조마을)"}) == [
        "봉조농촌체험학교",
        "봉조마을",
    ]


def test_parentheses_in_the_middle_are_removed():
    assert expand_synonyms({"village_name": "들국화(만수)마을"}) == ["들국화만수마을"]
    assert expand_synonyms({"village_name": "돌머리(석두)어촌체험휴양마을"}) == [
        "돌머리석두어촌체험휴양마을"
    ]


def test_synonym_with_many_spaces_keeps_one_space():
    assert expand_synonyms({"village_name": "곡성  목화  농어촌체험 휴양마을"}) == [
        "곡성 목화농어촌체험휴양마을"
    ]
    assert expand_synonyms({"village_name": "보성 예당 체험휴양마을"}) == ["보성 예당체험휴양마을"]
    assert expand_synonyms({"village_name": "하조 산달뱅이 마을"}) == ["하조 산달뱅이마을"]


def test_expand_synonyms_accepts_alias_list_and_missing_alias():
    assert expand_synonyms({"village_name": "예시 갯벌마을", "alias": ["갯벌마을"]}) == [
        "예시 갯벌마을",
        "갯벌마을",
    ]
    assert expand_synonyms({"village_name": "예시 갯벌마을"}) == ["예시 갯벌마을"]


def test_village_name_row_puts_id_first():
    rows, errors = build_village_name_rows(
        [{"village_id": "V001", "village_name": "예시 갯벌마을", "alias": "갯벌마을"}]
    )
    assert errors == []
    assert rows == [["V001", "예시 갯벌마을", "갯벌마을"]]


def test_empty_village_name_is_an_error():
    rows, errors = build_village_name_rows([{"village_id": "V001", "village_name": "  "}])
    assert rows == []
    assert errors == ["마을명이 비어 있음: V001"]


def test_same_village_synonym_duplicate_blocks_both_files(tmp_path):
    villages = [
        {
            "village_id": "V001",
            "village_name": "예시 갯벌마을",
            "alias": "예시 갯벌마을",
            "registration_code": "GB-001",
        }
    ]
    with pytest.raises(EntityExportError, match="예시 갯벌마을"):
        export_entity_csvs(villages, tmp_path)
    assert not (tmp_path / "village_name.csv").exists()
    assert not (tmp_path / "registration_code.csv").exists()


def test_synonym_shared_by_two_villages_is_an_error(tmp_path):
    villages = [
        {"village_id": "V001", "village_name": "갯벌마을", "alias": "체험마을"},
        {"village_id": "V002", "village_name": "무등마을", "alias": "체험마을"},
    ]
    try:
        export_entity_csvs(villages, tmp_path)
    except EntityExportError as exc:
        assert any("체험마을" in line and "V001" in line and "V002" in line for line in exc.errors)
    else:
        raise AssertionError("교차 중복은 실패해야 한다")
    assert list(tmp_path.glob("*.csv")) == []


def test_duplicate_village_id_and_registration_code_are_errors():
    from services.kakao_entity_export import validate_entries

    assert any(
        "V001" in line
        for line in validate_entries(
            [
                ["V001", "예시 갯벌마을"],
                ["V001", "다른 이름"],
            ]
        )
    )
    codes = build_registration_code_rows(
        [
            {"village_id": "V001", "registration_code": "GB-001"},
            {"village_id": "V002", "registration_code": "GB-001"},
        ]
    )
    assert codes == [["GB-001"], ["GB-001"]]
    assert any("GB-001" in line for line in validate_entries(codes))


def test_registration_code_skips_blank_and_omits_village_name():
    rows = build_registration_code_rows(
        [
            {"village_id": "V001", "village_name": "예시 갯벌마을", "registration_code": " GB-001 "},
            {"village_id": "V002", "village_name": "무등마을", "registration_code": ""},
            {"village_id": "V003", "village_name": "푸른바다마을"},
        ]
    )
    assert rows == [["GB-001"]]


def test_same_place_with_two_sido_names_keeps_one_row(tmp_path):
    villages = [
        {
            "village_id": "OLD",
            "village_name": "소포마을",
            "sigungu": "진도군",
            "address": "전라남도 진도군 지산면 지산민속로 791",
            "registration_code": "GB-001",
        },
        {
            "village_id": "NEW",
            "village_name": "소포마을",
            "sigungu": "진도군",
            "address": "전남광주통합특별시 진도군 지산면 지산민속로 791",
        },
    ]
    export_entity_csvs(villages, tmp_path)
    text = (tmp_path / "village_name.csv").read_text(encoding="utf-8-sig")
    assert text == "NEW,소포마을\n"
    assert (tmp_path / "registration_code.csv").read_text(encoding="utf-8-sig") == "GB-001\n"


def test_same_name_in_two_sigungu_gets_distinct_synonyms(tmp_path):
    villages = [
        {"village_id": "A", "village_name": "학동마을", "sigungu": "담양군"},
        {"village_id": "B", "village_name": "학동마을", "sigungu": "고흥군"},
    ]
    export_entity_csvs(villages, tmp_path)
    text = (tmp_path / "village_name.csv").read_text(encoding="utf-8-sig")
    assert text == "A,담양군 학동마을\nB,고흥군 학동마을\n"


def test_export_writes_headerless_utf8_csv(tmp_path):
    villages = [
        {
            "village_id": "V001",
            "village_name": "예시 갯벌마을",
            "alias": "갯벌마을",
            "registration_code": "GB-001",
        },
        {"village_id": "V002", "village_name": "무등마을"},
    ]
    export_entity_csvs(villages, tmp_path)
    village_bytes = (tmp_path / "village_name.csv").read_bytes()
    code_bytes = (tmp_path / "registration_code.csv").read_bytes()
    assert village_bytes.startswith(b"\xef\xbb\xbf")
    assert village_bytes.decode("utf-8-sig") == "V001,예시 갯벌마을,갯벌마을\nV002,무등마을\n"
    assert code_bytes.decode("utf-8-sig") == "GB-001\n"
    assert "village_id" not in village_bytes.decode("utf-8-sig")
    assert "예시 갯벌마을" not in code_bytes.decode("utf-8")
