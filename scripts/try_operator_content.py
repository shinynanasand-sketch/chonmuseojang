"""시연 운영자 마을에 고정 설명으로 소개글과 SNS 문구를 만든다. 키는 출력하지 않는다."""

import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT / ".env.local", override=False)

from services.demo_data import DEMO_VILLAGES  # noqa: E402
from services.operator_assistant import save_operator_contents  # noqa: E402
from services.supabase_client import get_operator_by_login_id  # noqa: E402

_LOGIN_ID = "owner_v001"
_DESCRIPTION = "가을에 아이와 조개를 잡아요"
_INTRO = "소개글"
_SNS = "SNS홍보문구"


def _other_demo_names(village_id: str) -> list[str]:
    names = []
    for row in DEMO_VILLAGES:
        if row.get("village_id") == village_id:
            continue
        name = str(row.get("village_name") or "").strip()
        if name:
            names.append(name)
            short = name.removeprefix("예시 ").strip()
            if short and short not in names:
                names.append(short)
    return names


def main() -> int:
    operator = get_operator_by_login_id(_LOGIN_ID)
    if not operator or not operator.get("village_id"):
        print("결과: 실패")
        print("운영자를 찾지 못했습니다.")
        return 1

    village_id = operator["village_id"]
    print(f"로그인 {_LOGIN_ID}")
    print(f"마을 {village_id}")
    print(f"설명: {_DESCRIPTION}")

    result = save_operator_contents(operator, _DESCRIPTION)
    contents = result.get("contents") or []
    by_type = {row.get("content_type"): str(row.get("body") or "").strip() for row in contents}
    intro = by_type.get(_INTRO, "")
    sns = by_type.get(_SNS, "")
    print(f"{_INTRO}: {intro}")
    print(f"{_SNS}: {sns}")

    foreign = [name for name in _other_demo_names(village_id) if name and (name in intro or name in sns)]
    own_village = all(row.get("village_id") == village_id for row in contents)
    ok = bool(result.get("saved")) and bool(intro) and bool(sns) and own_village and not foreign
    if foreign:
        print("다른 마을: " + ", ".join(foreign))
    print("결과: 통과" if ok else "결과: 실패")
    if not ok and result.get("message"):
        print(result["message"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
