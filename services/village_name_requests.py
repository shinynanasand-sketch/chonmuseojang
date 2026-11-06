"""마을 담당자가 요청한 보여줄 이름.

villages_cache.village_name은 공공데이터 원본이라 동기화가 다시 덮어쓴다.
마을 번호도 그 원본 이름으로 만들어져 있으므로 저장 값은 바꾸지 않는다.
"""

_ALIAS_SPLIT = (",", "、", "|", ";")

NAME_REQUESTS = [
    {
        "village_id": "PDeac2fe424e02",
        "official_name": "도선국사체험마을영농조합법인",
        "requested_name": "도선국사마을",
        "sigungu": "광양시",
        "requested_by": "마을 담당자",
        "changes": [
            {
                "label": "마을 소개, 지도, 추천, 홈 안내, 사무장 화면에 보이는 이름",
                "applied": True,
                "reason": "이 마을 번호의 화면 이름을 도선국사마을로 보여 줍니다.",
            },
            {
                "label": "카카오에서 새 이름으로 찾고 안내하는 문장",
                "applied": True,
                "reason": "도선국사마을로 말하면 이 마을을 찾습니다.",
            },
            {
                "label": "예전 법인명으로 같은 마을 찾기",
                "applied": True,
                "reason": "도선국사체험마을영농조합법인으로 말해도 같은 마을입니다.",
            },
            {
                "label": "마을 번호와 예약·운영자 연결",
                "applied": False,
                "reason": "마을 번호 PDeac2fe424e02와 예약·운영자 연결은 유지합니다.",
            },
            {
                "label": "공공데이터 저장 칸과 다음 동기화 원본",
                "applied": False,
                "reason": "저장 이름은 법인명 그대로입니다. 다음 동기화 뒤에도 화면 이름은 도선국사마을입니다.",
            },
            {
                "label": "오픈빌더 엔티티 재등록",
                "applied": False,
                "reason": "내보낼 때 새 이름과 법인명을 함께 넣습니다. 오픈빌더에 다시 올리는 작업은 하지 않았습니다.",
            },
        ],
    }
]


def request_for_village(village_id: str) -> dict | None:
    for request in NAME_REQUESTS:
        if request["village_id"] == village_id:
            return request
    return None


def request_for_spoken_name(spoken: str) -> dict | None:
    """요청한 새 이름만 마을 번호로 바로 찾는다. 법인명은 저장 조회에 맡긴다."""
    name = spoken.strip()
    for request in NAME_REQUESTS:
        if request["requested_name"] == name:
            return request
    return None


def present_village(row: dict) -> dict:
    """복사본의 마을명만 요청 이름으로 바꾼다. 요청이 없으면 같은 행을 돌려준다."""
    request = request_for_village(str(row.get("village_id") or ""))
    if request is None:
        return row
    shown = dict(row)
    shown["village_name"] = request["requested_name"]
    return shown


def present_villages(rows: list[dict]) -> list[dict]:
    return [present_village(row) for row in rows]


def village_names(row: dict) -> list[str]:
    """발화에서 이 행으로 볼 수 있는 마을명. 저장 이름과 요청 이름을 모두 포함한다."""
    names: list[str] = []
    stored = str(row.get("village_name") or "").strip()
    if stored:
        names.append(stored)
    request = request_for_village(str(row.get("village_id") or ""))
    if request is None:
        return names
    for extra in (request["requested_name"], request["official_name"]):
        if extra and extra not in names:
            names.append(extra)
    return names


def matches_spoken_village(row: dict, spoken: str) -> bool:
    text = spoken.strip()
    if not text:
        return False
    names = village_names(row)
    if text in names:
        return True
    sigungu = str(row.get("sigungu") or "").strip()
    if not sigungu:
        return False
    return any(text == f"{name} {sigungu}" or text == f"{sigungu} {name}" for name in names)


def export_village(row: dict) -> dict:
    """엔티티로 내보낼 때 새 이름을 앞에 두고 법인명을 동의어로 붙인다."""
    request = request_for_village(str(row.get("village_id") or ""))
    if request is None:
        return row
    updated = dict(row)
    updated["village_name"] = request["requested_name"]
    updated["alias"] = _alias_with_official(row.get("alias"), request["official_name"])
    return updated


def _alias_with_official(alias, official: str) -> str | list[str]:
    if isinstance(alias, list):
        tokens = [str(item).strip() for item in alias if str(item).strip()]
        if official not in tokens:
            tokens.append(official)
        return tokens
    text = str(alias or "").strip()
    if not text:
        return official
    parts = [text]
    for mark in _ALIAS_SPLIT:
        next_parts: list[str] = []
        for part in parts:
            next_parts.extend(piece.strip() for piece in part.split(mark))
        parts = [piece for piece in next_parts if piece]
    if official in parts:
        return text
    return f"{text}|{official}"
