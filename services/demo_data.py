"""시연용 샘플 데이터 (공공 API 미설정 시 폴백)."""

DEMO_VILLAGE_IDS = frozenset({"V001", "V002", "V004"})


def is_demo_village(row: dict) -> bool:
    """시연용 예시 마을인지 판별한다. 운영자 테스트 시드는 저장소에 남겨 둔다."""
    village_id = str(row.get("village_id") or "")
    name = str(row.get("village_name") or "")
    return village_id in DEMO_VILLAGE_IDS or name.startswith("예시 ")


def public_village_rows(rows: list[dict]) -> list[dict]:
    """실마을이 있으면 예시 마을을 공개 목록에서 뺀다. 예시만 있으면 그대로 둔다."""
    if any(not is_demo_village(row) for row in rows):
        return [row for row in rows if not is_demo_village(row)]
    return list(rows)


DEMO_VILLAGES = [
    {
        "village_id": "V001",
        "village_name": "예시 갯벌마을",
        "sido": "전라남도",
        "sigungu": "신안군",
        "program_type": "갯벌체험",
        "latitude": 34.9,
        "longitude": 126.1,
        "grade": "으뜸촌",
        "trust_score": 82,
    },
    {
        "village_id": "V002",
        "village_name": "예시 무등마을",
        "sido": "광주광역시",
        "sigungu": "북구",
        "program_type": "농사체험",
        "latitude": 35.18,
        "longitude": 126.91,
        "trust_score": 65,
    },
    {
        "village_id": "V004",
        "village_name": "예시 여수마을",
        "sido": "전남광주통합특별시",
        "sigungu": "여수시",
        "program_type": "어촌체험",
        "latitude": 34.76,
        "longitude": 127.66,
        "trust_score": 70,
    },
]

DEMO_OPERATORS = [
    {
        "village_id": "V001",
        "kakao_user_id": "kakao_owner_v001",
        "login_id": "owner_v001",
        "operator_name": "V001 운영자",
        "registered_at": "2026-09-01T00:00:00+00:00",
        "is_active": True,
    },
    {
        "village_id": "V002",
        "kakao_user_id": "kakao_owner_v002",
        "login_id": "owner_v002",
        "operator_name": "V002 운영자",
        "registered_at": "2026-09-01T00:00:00+00:00",
        "is_active": True,
    },
]
