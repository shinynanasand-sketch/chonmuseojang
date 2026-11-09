"""현장 변경 건수와 주요 변경 요약.

줄 단위 표는 field_changes.guide_rows()가 만든다.
이 모듈은 그 줄을 구분으로 묶어 건수와 한 장 요약을 만든다.
문서의 큰 변경은 이용에 보이는 문장만 둔다.
"""

from services.field_changes import guide_rows

_DETAIL = "/guide/name-requests"

_GROUP_ORDER = (
    "마을명",
    "체험 추가",
    "가격",
    "운영 중지",
    "예약 현황",
    "체험 달력",
    "단체 이름",
    "체험 묶음",
)

_GROUP_COPY = {
    "마을명": (
        "화면 이름을 도선국사마을로 보여 주고, 그 이름으로 찾는다. "
        "마을 번호, 공공데이터 저장 이름, 오픈빌더 재등록은 그대로 둔다."
    ),
    "체험 추가": "가격표의 천연염색 세 가지를 목록 뒤에 붙인다.",
    "가격": "1인 금액을 체험객 화면에 보이고, 예약 합계는 그 금액에 인원을 곱한다.",
    "운영 중지": "가격이 없는 체험은 중지로 두고, 사무장이 다시 운영으로 바꿀 수 있다.",
    "예약 현황": "방문일이 속한 한 주를 보고, 이전 주와 다음 주로 움직인다.",
    "체험 달력": "이번 달 대기·승인·거절 건수와 달력을 보여 준다.",
    "단체 이름": "체험객이 달력에 단체 이름을 넣고, 단체가 아니면 없음을 넣는다.",
    "체험 묶음": (
        "사무장이 내 마을에서 프로그램 목록과 같은 체험을 한 줄로 보고, "
        "담당 카드에서 이름을 찾아 더한다. 그 담당은 묶인 체험의 달력과 글을 본다."
    ),
}

# 마을명 카드가 이미 설명하는 미적용을 빼고, 남은 미적용만 한 장으로 묶는다.
_HELD_KINDS = ("공공데이터", "오픈빌더")
_HELD_KIND = "적용하지 않은 나머지"
_HELD_COPY = "추가 체험을 공공데이터 원본에 넣지 않고, 오픈빌더에 주 이동 버튼을 넣지 않았다."

MAJOR_CHANGES = (
    {
        "title": "카카오 채널 하나에서 체험객과 사무장을 나눈다.",
        "body": "마을 이름과 코드로 사무장이 등록한다.",
    },
    {
        "title": "예약은 저장하고, 승인과 거절은 사무장이 한다.",
        "body": "챗봇이 먼저 알림을 보내지 않는다.",
    },
    {
        "title": "마을 추천에 한 줄 이유를 붙인다.",
        "body": "한 모델이 바로 거절하면 다른 모델로 한 번 바꾼다.",
    },
    {
        "title": "카카오 사진으로 소개와 SNS 초안을 만든다.",
        "body": "사무장이 확인한 뒤에 마을 화면에 공개한다.",
    },
    {
        "title": "지금 하지 않는 체험만 사무장이 중지한다.",
        "body": "추천 문장은 그 항목만 운영하지 않는다고 말한다.",
    },
    {
        "title": "사무장과 체험 담당을 나눈다.",
        "body": "체험 달력은 단체와 인원이고, 승인은 사무장만 한다.",
    },
    {
        "title": "한 담당이 여러 체험을 맡는다.",
        "body": "사무장이 내 마을에서 체험을 묶어 옮긴다.",
    },
    {
        "title": "홈은 예약 방법, 사무장이 있는 마을, 채널 QR을 보여 준다.",
        "body": "검색에는 공개 화면만 알린다.",
    },
    {
        "title": "전국 농촌여행 포털을 대신하지 않는다.",
        "body": "광주·전남 마을의 예약과 홍보를 맡는다.",
    },
)


def _bucket() -> dict:
    return {"count": 0, "applied": 0}


def _count_rows(rows: list[dict]) -> dict[str, dict]:
    by_kind: dict[str, dict] = {}
    for row in rows:
        kind = str(row["kind"])
        stats = by_kind.setdefault(kind, _bucket())
        stats["count"] += 1
        if row["applied"]:
            stats["applied"] += 1
    return by_kind


def _group(kind: str, stats: dict, body: str) -> dict:
    return {
        "kind": kind,
        "count": stats["count"],
        "applied": stats["applied"],
        "body": body,
        "detail_href": _DETAIL,
    }


def change_summary() -> dict:
    """구분별 건수와 큰 변경. 표에 없는 구분이 생기면 요약을 다시 적도록 멈춘다."""
    rows = guide_rows()
    by_kind = _count_rows(rows)
    known = set(_GROUP_ORDER) | set(_HELD_KINDS)
    unknown = [kind for kind in by_kind if kind not in known]
    if unknown:
        raise ValueError(f"요약에 없는 현장 변경 구분: {', '.join(unknown)}")
    missing = [kind for kind in known if kind not in by_kind]
    if missing:
        raise ValueError(f"현장 변경 구분 없음: {', '.join(missing)}")

    groups = []
    for kind in _GROUP_ORDER:
        groups.append(_group(kind, by_kind[kind], _GROUP_COPY[kind]))

    held = _bucket()
    for kind in _HELD_KINDS:
        stats = by_kind[kind]
        if stats["applied"]:
            raise ValueError(f"적용하지 않은 묶음에 적용된 줄이 있습니다: {kind}")
        held["count"] += stats["count"]
    groups.append(_group(_HELD_KIND, held, _HELD_COPY))

    total = len(rows)
    applied = sum(stats["applied"] for stats in by_kind.values())
    not_applied = total - applied
    name_held = by_kind["마을명"]["count"] - by_kind["마을명"]["applied"]
    if name_held + held["count"] != not_applied:
        raise ValueError("적용하지 않은 건수가 마을명과 나머지 묶음에 다 들어가지 않습니다.")
    if sum(group["count"] for group in groups) != total:
        raise ValueError("묶음 건수 합이 전체 건수와 다릅니다.")

    return {
        "total": total,
        "applied": applied,
        "not_applied": not_applied,
        "groups": groups,
        "major": [{"title": item["title"], "body": item["body"]} for item in MAJOR_CHANGES],
    }
