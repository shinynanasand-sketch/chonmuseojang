"""현장에서 요청한 체험 추가, 1인 가격, 운영 중지.

공공데이터 program_name은 동기화가 다시 덮으므로 이 모듈에만 둔다.
"""

from datetime import datetime, timedelta, timezone

from services.village_name_requests import NAME_REQUESTS

VILLAGE_ID = "PDeac2fe424e02"
VILLAGE_NAME = "도선국사마을"
# 이 시각보다 앞선 운영 중 기록은 가격이 없는 체험의 처음 중지로 본다.
# 그 뒤에 사무장이 운영으로 저장한 값은 그대로 둔다.
STOP_RECORD_AT = datetime(2026, 11, 7, 6, 0, tzinfo=timezone(timedelta(hours=9)))

_EXTRAS = (
    {"label": "천연염색(에코백)", "price": 18000, "sheet": "천연염색(에코백)"},
    {"label": "천연염색(크로스백)", "price": 18000, "sheet": "천연염색(크로스백)"},
    {"label": "천연염색(삼각스카프-일반)", "price": 18000, "sheet": "천연염색(삼각스카프-일반)"},
)

_PRICES = (
    {"label": "감수확", "price": 10000, "sheet": "감수확체험"},
    {"label": "천연염색(손수건)", "price": 12000, "sheet": "천연염색(손수건)"},
    {"label": "천연염색(삼각스카프쪽염색)", "price": 25000, "sheet": "천연염색(삼각스카프-쪽염색)"},
    {"label": "천연염색(삼각스카프감염색)", "price": 20000, "sheet": "천연염색(삼각스카프-강염색)"},
    {"label": "천연염색(사각스카프감+쪽염색)", "price": 32000, "sheet": "천연염색(사각스카프-감염색,쪽염색)"},
    {"label": "전통손두부만들기", "price": 12000, "sheet": "전통손두부만들기"},
    {"label": "인절미떡메치기", "price": 15000, "sheet": "인절미만들기"},
    {"label": "오색비빔밥", "price": 10000, "sheet": "비빔밥"},
    {"label": "향토음식(한상)", "price": 15000, "sheet": "향토음식(한상차림)"},
    {"label": "향토음식(뷔페)", "price": 10000, "sheet": "향토음식(뷔페)"},
    {"label": "향낭만들기", "price": 17000, "sheet": "향낭만들기"},
    {"label": "천연염색(파우치)", "price": 15000, "sheet": "천연염색(파우치)"},
    {"label": "고구마수확", "price": 10000, "sheet": "고구마수확체험"},
    {"label": "매실쌀강정만들기", "price": 12000, "sheet": "매실쌀강정만들기"},
    {"label": "부채한국화그리기", "price": 13000, "sheet": "부채한국화그리기"},
    {"label": "감자수확", "price": 10000, "sheet": "감자수확체험"},
)

_STOPS = (
    "양파수확",
    "천연염색(인견이불)",
    "천연염색(바지)",
    "부채한국화그리기(오죽)",
)

_PRICE_ROWS = _PRICES + _EXTRAS
_PRICE_BY_LABEL = {item["label"]: item["price"] for item in _PRICE_ROWS}


def won(amount: int) -> str:
    return f"{amount:,}원"


def _known(village_id: str) -> bool:
    return str(village_id or "") == VILLAGE_ID


def extra_labels(village_id: str) -> list[str]:
    if not _known(village_id):
        return []
    return [item["label"] for item in _EXTRAS]


def has_price_table(village_id: str) -> bool:
    return _known(village_id)


def price_of(village_id: str, label: str) -> int | None:
    if not _known(village_id):
        return None
    return _PRICE_BY_LABEL.get(str(label or "").strip())


def stop_labels(village_id: str) -> frozenset[str]:
    if not _known(village_id):
        return frozenset()
    return frozenset(_STOPS)


def line_total(village_id: str, label: str, num_people) -> int | None:
    """예약 한 건의 합계. 1인 금액에 인원을 곱하고, 가격이 없으면 비운다."""
    price = price_of(village_id, label)
    if price is None:
        return None
    try:
        count = int(num_people)
    except (TypeError, ValueError):
        return None
    if count < 1:
        return None
    return price * count


def status_is_before_record(value) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return True
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment < STOP_RECORD_AT


def _village_cell(name: str, village_id: str) -> str:
    return f"{name} {village_id}"


def _row(village: str, kind: str, request: str, result: str, applied: bool) -> dict:
    return {
        "village": village,
        "kind": kind,
        "request": request,
        "result": result,
        "applied": applied,
    }


def guide_rows() -> list[dict]:
    """심사자가 보는 현장 변경 기록. 동작과 같은 목록에서 만든다."""
    rows: list[dict] = []
    for request in NAME_REQUESTS:
        village = _village_cell(request["requested_name"], request["village_id"])
        for change in request["changes"]:
            rows.append(
                _row(
                    village,
                    "마을명",
                    change["label"],
                    change["reason"],
                    bool(change["applied"]),
                )
            )
    village = _village_cell(VILLAGE_NAME, VILLAGE_ID)
    for item in _EXTRAS:
        rows.append(
            _row(
                village,
                "체험 추가",
                f"가격표의 {item['sheet']}을 체험으로 등록",
                f"공공데이터 목록 뒤에 {item['label']}을 붙입니다.",
                True,
            )
        )
    rows.append(
        _row(
            village,
            "공공데이터",
            "추가한 체험을 공공데이터 프로그램 이름에 넣기",
            "저장 칸은 바꾸지 않습니다. 다음 동기화 뒤에도 추가 체험은 화면 목록 뒤에 붙습니다.",
            False,
        )
    )
    for item in _PRICE_ROWS:
        price = won(item["price"])
        if item["sheet"] == item["label"]:
            request = f"{item['sheet']} 1인 {price}"
            result = f"체험객 화면에는 1인 {price}이 보입니다. 예약 한 건의 합계는 이 금액에 인원을 곱합니다."
        else:
            request = f"가격표 이름 {item['sheet']} 1인 {price}"
            result = (
                f"등록 이름 {item['label']}에 1인 {price}을 붙입니다. "
                "체험객 화면에는 단가가 보이고, 예약 한 건의 합계는 이 금액에 인원을 곱합니다."
            )
        rows.append(_row(village, "가격", request, result, True))
    for label in _STOPS:
        rows.append(
            _row(
                village,
                "운영 중지",
                f"{label}은 가격표에 금액이 없습니다.",
                "운영 여부를 중지로 저장합니다. 사무장이 다시 운영으로 바꿀 수 있습니다. 가격이 생기기 전에는 체험객 예약 목록에 넣지 않습니다.",
                True,
            )
        )
    screen = "카카오 사무장"
    rows.append(
        _row(
            screen,
            "예약 현황",
            "예약현황 조회는 최근 예약을 1주일 단위로 보는 화면으로 나눕니다.",
            "방문일이 속한 일요일부터 토요일까지를 답장으로 보여 줍니다. 이번 주, 이전 주, 다음 주로 이동합니다. 이전 주를 다시 누르면 한 주 더 돌아갑니다. 달력 버튼은 붙이지 않습니다.",
            True,
        )
    )
    rows.append(
        _row(
            screen,
            "체험 달력",
            "체험 달력 조회는 달력과 함께 한 달 예약 현황을 보는 화면으로 나눕니다.",
            "답장은 이번 달 대기, 승인, 거절 건수와 달력 열기입니다. 달력 목록은 열린 달만 보여 줍니다. 다른 달 대기는 그 달로 이동해 승인하거나 거절합니다.",
            True,
        )
    )
    rows.append(
        _row(
            screen,
            "오픈빌더",
            "이번 주, 이전 주, 다음 주 버튼을 예약 현황 조회 블록으로 받게 합니다.",
            "서버는 이번 주, 이전 주, 다음 주를 받아 그 주를 보여 줍니다. 오픈빌더 블록에 이 세 발화를 넣는 작업은 하지 않았습니다.",
            False,
        )
    )
    rows.append(
        _row(
            "체험 달력",
            "단체 이름",
            "마을 운영자가 단체 일정을 텍스트로 넣지 않고, 체험객 달력에서 단체 이름을 입력합니다. 단체가 아니면 없음을 입력합니다.",
            "운영자 달력에서는 단체 이름을 받지 않습니다. 체험객이 적은 단체 이름은 예약에 저장되고, 없음도 예약으로 남습니다. 빈 칸은 예약하지 않고 없음을 입력하라는 안내를 보여 줍니다. 운영자 달력과 예약 현황에 그 이름이 보입니다.",
            True,
        )
    )
    rows.append(
        _row(
            "내 마을",
            "체험 묶음",
            "여러 체험을 한 담당자가 맡도록 묶는다.",
            "사무장이 내 마을 화면에서 등록된 담당에게 체험을 붙입니다. 그 담당은 묶인 체험의 달력과 글을 봅니다. 체험이 바뀌면 맡지 않은 체험이 다시 나타납니다.",
            True,
        )
    )
    rows.append(
        _row(
            "내 마을",
            "체험 묶음",
            "담당 화면에서 마을 체험이 모두 보이게 한다.",
            "체험 담당은 프로그램 목록과 같은 체험을 한 줄로 보여 준다. 담당이 없는 체험도 그 줄에 있다.",
            True,
        )
    )
    rows.append(
        _row(
            "내 마을",
            "체험 묶음",
            "담당 카드에서 체험을 찾아 더한다.",
            "입력한 이름과 맞는 담당 없는 체험을 그 담당에게 붙입니다. 빼면 담당 없음으로 돌아갑니다.",
            True,
        )
    )
    rows.append(
        _row(
            "카카오 사무장",
            "시연",
            "촬영과 심사에서 카카오 계정 하나로 체험객, 사무장, 체험 담당을 바꿔 본다.",
            "발표 모드에서 시연 역할로 바꿉니다. 저장된 사무장 등록은 그대로 둡니다. 예시 갯벌마을에 소금체험과 조개잡이를 더하고, 시연 담당 한 명을 둡니다. 심사 계정은 그 계정이 만든 예약만 다룹니다.",
            True,
        )
    )
    return rows
