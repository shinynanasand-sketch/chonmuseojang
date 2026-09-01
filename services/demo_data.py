"""시연용 샘플 데이터 (공공 API 미설정 시 폴백)."""

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
        "display_name": "V001 운영자",
        "is_active": True,
    },
    {
        "village_id": "V002",
        "kakao_user_id": "kakao_owner_v002",
        "login_id": "owner_v002",
        "display_name": "V002 운영자",
        "is_active": True,
    },
]
